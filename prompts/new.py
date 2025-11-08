# Import libraries
import os
import sys
import whisper
import logging
import requests
import datetime
import re
import hashlib
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Attempt to import dateutil, warn if not found
try:
    from dateutil.relativedelta import relativedelta
    dateutil_available = True
except ImportError:
    dateutil_available = False

# Set up logging
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = 'transcription_log.log'
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
logger = logging.getLogger("TranscriptionApp")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

# Folders
INPUT_AUDIO_FOLDER = "input_audio"       # Put your local files here
AUDIO_FOLDER = "audio_files"             # Used to store files downloaded from URLs
ANALYSIS_FOLDER = "analysis_results"     # Where analysis is saved
os.makedirs(INPUT_AUDIO_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(ANALYSIS_FOLDER, exist_ok=True)

# Recognized audio/video extensions
AUDIO_EXTS = ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.mp4', '.mov', '.wmv', '.avi', '.mkv', '.webm')

def is_url(s: str) -> bool:
    return isinstance(s, str) and s.strip().lower().startswith(('http://', 'https://'))

# Whisper model
try:
    model = whisper.load_model("base")
    logger.info("Whisper model 'base' loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    logger.error("Ensure PyTorch and ffmpeg are installed and configured.")
    sys.exit(1)

# Deepseek API key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# --- Helpers ---

def read_urls_from_file(file_name='urls3.txt'):
    if not os.path.exists(file_name):
        logger.warning(f"URL file not found: {file_name}")
        return []
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            urls = [ln.strip() for ln in file if ln.strip() and not ln.strip().startswith('#')]
        logger.info(f"Read {len(urls)} URLs from {file_name}")
        return urls
    except Exception as e:
        logger.exception(f"Error reading URL file {file_name}: {e}")
        return []

def find_audio_files_in_folder(folder):
    """Return a list of full paths to audio/video files in the folder (recursive)."""
    found = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(AUDIO_EXTS):
                found.append(os.path.join(root, f))
    return found

# --- Core functions from your existing flow, extended to support local files ---

def download_audio(url, output_folder):
    """Download file from URL to output_folder, return local path or None."""
    if not url.startswith(('http://', 'https://')):
        logger.warning(f"URL not valid: {url}")
        return None
    try:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        path_hint = "recording"
        try:
            parsed_url = urlparse(url)
            path_part = parsed_url.path.strip('/')
            if path_part:
                base_hint = os.path.basename(path_part)
                if base_hint and base_hint != '/':
                    path_hint = re.sub(r'[^a-zA-Z0-9_-]+', '_', base_hint)
                    path_hint = re.sub(r'_+', '_', path_hint).strip('_')
                    path_hint = path_hint[:30]
        except Exception as parse_err:
            logger.debug(f"Could not parse path hint from URL {url}: {parse_err}")

        file_base_name_unique = f"{path_hint}_{url_hash}"

        # Decide extension
        assumed_ext = ".mp3"
        final_extension = assumed_ext
        try:
            original_ext = os.path.splitext(os.path.basename(unquote(urlparse(url).path)))[1].lower()
            if original_ext and original_ext in AUDIO_EXTS:
                final_extension = original_ext
            elif original_ext:
                logger.warning(f"Unusual extension '{original_ext}', using {assumed_ext}.")
        except Exception as ext_err:
            logger.error(f"Error extracting extension, defaulting to {assumed_ext}: {ext_err}")

        safe_file_name = f"{file_base_name_unique}{final_extension}"
        safe_file_name = re.sub(r'[\\/*?:"<>|]+', '_', safe_file_name)
        safe_file_name = re.sub(r'[^a-zA-Z0-9._-]+', '_', safe_file_name)
        safe_file_name = re.sub(r'_+', '_', safe_file_name).strip('._')
        if not safe_file_name:
            safe_file_name = f"download_{url_hash}{final_extension}"

        max_len = 150
        if len(safe_file_name) > max_len:
            name, ext = os.path.splitext(safe_file_name)
            ext = ext[:10]
            safe_file_name = name[:max_len - len(ext)] + ext

        audio_file_path = os.path.join(output_folder, safe_file_name)

        counter = 1
        base_name_part, ext_part = os.path.splitext(safe_file_name)
        while os.path.exists(audio_file_path):
            audio_file_path = os.path.join(output_folder, f"{base_name_part}_{counter}{ext_part}")
            counter += 1

        logger.info(f"Downloading: {url} -> {audio_file_path}")
        with requests.Session() as session:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = session.get(url, timeout=60, stream=True, headers=headers, allow_redirects=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            chunk_size = 8192
            with open(audio_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)

            if total_size != 0 and bytes_downloaded != total_size:
                logger.warning(f"Downloaded size mismatch for {audio_file_path}")

        logger.info(f"Downloaded to {audio_file_path}")
        return audio_file_path

    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading: {url}")
        return None
    except requests.exceptions.RequestException as e:
        status_code_info = f" (Status {e.response.status_code})" if getattr(e, 'response', None) else ""
        logger.error(f"Failed to download {url}: {e}{status_code_info}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error downloading {url}: {e}")
        if 'audio_file_path' in locals() and os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                logger.info(f"Removed partial file: {audio_file_path}")
            except OSError:
                pass
        return None

def transcribe_audio(file_path):
    if not file_path or not os.path.exists(file_path):
        logger.error(f"File not found for transcription: {file_path}")
        return ""
    try:
        if os.path.getsize(file_path) == 0:
            logger.error(f"File is empty, skipping: {file_path}")
            return ""
    except OSError as e:
        logger.error(f"Could not get size for {file_path}: {e}")
        return ""
    logger.info(f"Transcribing: {file_path}")
    try:
        result = model.transcribe(file_path, fp16=False)
        transcript_text = result.get("text", "").strip()
        if not transcript_text:
            logger.warning(f"Empty transcript for: {file_path}")
        else:
            logger.info(f"Transcription complete: {os.path.basename(file_path)}")
        return transcript_text
    except Exception as e:
        logger.exception(f"Whisper transcription failed for {file_path}: {e}")
        return ""

def analyze_transcript_with_llm(transcript, audio_filename):
    if not transcript:
        logger.warning(f"Skipping analysis for {audio_filename}: empty transcript.")
        return "Analysis skipped: Empty transcript provided."
    if not DEEPSEEK_API_KEY or len(DEEPSEEK_API_KEY) < 10:
        logger.error("Deepseek API key missing/invalid. Skipping analysis.")
        return "Analysis failed: Deepseek API key not set or invalid."

    logger.info(f"Analyzing transcript for: {audio_filename}")
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        today = datetime.date.today()
        cutoff_date_str = "April 24, 1944"
        if dateutil_available:
            try:
                cutoff_date = today - relativedelta(years=81)
                cutoff_date_str = cutoff_date.strftime("%B %d, %Y")
            except Exception:
                pass

        prompt_content = f"""
Analyze the following call transcript:
--- TRANSCRIPT START ---
{transcript}
--- TRANSCRIPT END ---

Your Objectives:

1. Billable Call Determination:
Assess whether the call is billable based SOLELY on the following criteria. Do NOT consider sales outcomes.

Criteria for a Non-Billable Call (Must meet one or more):
    1. Unqualified Customer:
        - Age 81+ (Born on or before {cutoff_date_str}).
        - Lives in nursing home/assisted living.
        - No active bank account/credit card.
        - Needs Power of Attorney for financial decisions.
    2. Vulgar or Prank Call:
        - Clearly wasting agent's time (irrelevant/disruptive).
        - Uses vulgar language.
    3. Do Not Call (DNC) Request:
        - Explicitly requests DNC list placement.
        - Calls only to complain about receiving calls.

Output for Billability:
- Billable: [Yes/No]
- Reason (if Not Billable): [State the specific criterion met, e.g., "Unqualified Customer: Age 81+"]

2. Sale or Application Submitted Determination:
Analyze if a final expense application was submitted, based on these definitions. This is SEPARATE from billability.

Criteria for Final Expense Application Submitted (Must meet ALL applicable points):
    - Requires collection of:
        - Portion of SSN (last 4, first 5, or full 9).
        - Checking/Savings account (Routing & Account #) OR Credit Card Number.
 
Output for Application Submission:
- Application Submitted: [Yes/No]
- Reason (if No): [Explain why, referencing the criteria, e.g., "No payment info collected", "No confirmation of submission mentioned"]

3. Supporting Information (Extract if available, state "Not Provided" otherwise):
    - Monthly Premium: [Amount or "Not Provided"]
    - Carrier: [Name or "Not Provided"]
    - Customer Name: [Full Name or "Not Provided"]
    - Phone Number: [Number or "Not Provided"]
    - Agent Name: [First Name or "Not Provided"]

4. Abrupt Ending Analysis:
    - Did the call end abruptly? [Yes/No]
    - Reason (if Yes): [Brief explanation, e.g., "Customer hung up", "Call dropped"]
    - Last Thing Said: [Quote the last audible statement]

--- IMPORTANT INSTRUCTIONS ---
Provide ONLY the structured output based on the format defined above, starting directly with "- Billable:".
Do NOT include any introductory sentences, concluding remarks, summaries, or markdown formatting.
Ensure every field listed under 'Output for Billability', 'Output for Application Submission', 'Supporting Information', and 'Abrupt Ending Analysis' is present in your response, even if the value is 'No' or 'Not Provided'.
"""
        messages = [
            {"role": "system", "content": "You are an AI assistant analyzing call transcripts. Provide ONLY the requested structured data."},
            {"role": "user", "content": prompt_content}
        ]
        data = {
            "messages": messages,
            "model": "deepseek-chat",
            "max_tokens": 1024,
            "temperature": 0.1,
            "stream": False,
        }
        api_endpoint = "https://api.deepseek.com/v1/chat/completions"
        response = requests.post(api_endpoint, headers=headers, json=data, timeout=90)
        response.raise_for_status()
        result = response.json()
        if "choices" in result and result["choices"] and "message" in result["choices"][0]:
            analysis_content = result["choices"][0]["message"].get("content", "").strip()
            return analysis_content or "Analysis failed: Empty response from API."
        return "Analysis failed: Unexpected API response format."
    except requests.exceptions.Timeout:
        return "Analysis failed: API request timed out"
    except requests.exceptions.HTTPError as http_err:
        try:
            details = response.json()
            msg = details.get('error', {}).get('message', '') if isinstance(details, dict) else ''
        except Exception:
            msg = response.text[:200]
        return f"Analysis failed: API Error {response.status_code}. {msg}"
    except Exception as e:
        logger.exception(f"LLM analysis error for {audio_filename}: {e}")
        return f"Analysis failed: Unexpected error ({type(e).__name__})"

def save_analysis_to_file(analysis_content, base_filename, analysis_folder):
    try:
        analysis_filename = f"{os.path.splitext(base_filename)[0]}_analysis.txt"
        analysis_filepath = os.path.join(analysis_folder, analysis_filename)
        with open(analysis_filepath, 'w', encoding='utf-8') as f:
            f.write(analysis_content)
        logger.info(f"Analysis saved to: {analysis_filepath}")
        return True
    except Exception as e:
        logger.exception(f"Failed to save analysis for {base_filename}: {e}")
        return False

# --- Processing logic ---

def process_local_file(file_path, analysis_folder=ANALYSIS_FOLDER):
    """Transcribe + analyze a local file. Does not delete the original."""
    audio_filename = os.path.basename(file_path)
    transcript = transcribe_audio(file_path)
    if not transcript:
        logger.error(f"Transcription failed or empty for {audio_filename}.")
        return "Transcription Failed"
    analysis_result = analyze_transcript_with_llm(transcript, audio_filename)
    if "Analysis failed" in analysis_result:
        logger.error(f"Analysis failed for {audio_filename}: {analysis_result}")
        return "Analysis Failed"
    if "Analysis skipped" in analysis_result:
        logger.warning(f"Analysis skipped for {audio_filename}.")
        return "Analysis Skipped"
    if save_analysis_to_file(analysis_result, audio_filename, analysis_folder):
        return "Analysis Success"
    return "Save Analysis Failed"

def process_local_folder(input_folder=INPUT_AUDIO_FOLDER, analysis_folder=ANALYSIS_FOLDER):
    files = find_audio_files_in_folder(input_folder)
    if not files:
        logger.info(f"No audio/video files found in '{input_folder}'.")
        return
    logger.info(f"Found {len(files)} files in '{input_folder}'. Starting processing...")
    status_counts = {
        "Analysis Success": 0,
        "Transcription Failed": 0,
        "Analysis Failed": 0,
        "Analysis Skipped": 0,
        "Save Analysis Failed": 0,
        "Critical Error": 0,
    }
    for i, path in enumerate(files, 1):
        logger.info(f"--- Local file {i}/{len(files)} --- {path}")
        try:
            status = process_local_file(path, analysis_folder)
        except Exception as e:
            logger.exception(f"Critical error processing {path}: {e}")
            status = "Critical Error"
        status_counts[status] = status_counts.get(status, 0) + 1

    logger.info("=" * 70)
    logger.info("Local Files Summary:")
    logger.info(f"Total Files: {len(files)}")
    for status, count in status_counts.items():
        if count:
            logger.info(f"- {status}: {count}")
    logger.info("=" * 70)

def process_url_item(url, audio_folder=AUDIO_FOLDER, analysis_folder=ANALYSIS_FOLDER):
    """Download URL, transcribe, analyze, save, then delete the downloaded file."""
    audio_file_path = download_audio(url, audio_folder)
    if not audio_file_path:
        return "Download Failed"
    audio_filename = os.path.basename(audio_file_path)
    try:
        transcript = transcribe_audio(audio_file_path)
        if not transcript:
            return "Transcription Failed"
        analysis_result = analyze_transcript_with_llm(transcript, audio_filename)
        if "Analysis failed" in analysis_result:
            return "Analysis Failed"
        if "Analysis skipped" in analysis_result:
            return "Analysis Skipped"
        return "Analysis Success" if save_analysis_to_file(analysis_result, audio_filename, analysis_folder) else "Save Analysis Failed"
    except Exception as e:
        logger.exception(f"Critical error processing URL {url}: {e}")
        return "Critical Error"
    finally:
        try:
            if os.path.exists(audio_file_path):
                os.remove(audio_file_path)
                logger.info(f"Cleaned up downloaded file: {audio_file_path}")
        except OSError as e:
            logger.error(f"Error removing file {audio_file_path}: {e}")

def process_urls_file(url_file='urls3.txt', audio_folder=AUDIO_FOLDER, analysis_folder=ANALYSIS_FOLDER):
    urls = read_urls_from_file(url_file)
    if not urls:
        logger.info("No URLs to process.")
        return
    logger.info(f"Starting processing for {len(urls)} URLs from {url_file}...")
    status_counts = {
        "Analysis Success": 0,
        "Download Failed": 0,
        "Transcription Failed": 0,
        "Analysis Failed": 0,
        "Analysis Skipped": 0,
        "Save Analysis Failed": 0,
        "Critical Error": 0,
    }
    for i, url in enumerate(urls, 1):
        logger.info(f"--- URL {i}/{len(urls)} --- {url}")
        status = process_url_item(url, audio_folder, analysis_folder)
        status_counts[status] = status_counts.get(status, 0) + 1

    logger.info("=" * 70)
    logger.info("URL Summary:")
    logger.info(f"Total URLs: {len(urls)}")
    for status, count in status_counts.items():
        if count:
            logger.info(f"- {status}: {count}")
    logger.info("=" * 70)

# --- Main ---

if __name__ == "__main__":
    logger.info("Script started.")
    if not dateutil_available:
        logger.warning("python-dateutil not found; age cutoff will be approximated.")

    # If there are files in input_audio, process them first; otherwise, read urls3.txt
    local_files = find_audio_files_in_folder(INPUT_AUDIO_FOLDER)
    if local_files:
        process_local_folder(INPUT_AUDIO_FOLDER, ANALYSIS_FOLDER)
    else:
        logger.info(f"No files found in '{INPUT_AUDIO_FOLDER}'. Looking for URLs in urls3.txt...")
        process_urls_file('urls3.txt', AUDIO_FOLDER, ANALYSIS_FOLDER)

    logger.info("Script finished.")
