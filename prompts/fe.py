# Import libraries
import os
import whisper # Keep one import
import logging
import requests
import datetime # Added for date calculation
import re # Added for regex operations
import hashlib # <--- ADD THIS LINE
from urllib.parse import urlparse, unquote # Added for URL parsing and decoding
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
# Configure logging to output to both console and a file
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Added logger name
log_file = 'transcription_log.log'

# File Handler
file_handler = logging.FileHandler(log_file, encoding='utf-8') # Specify encoding
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# Get the logger
logger = logging.getLogger("TranscriptionApp")
logger.setLevel(logging.INFO)
# Prevent adding handlers multiple times if the script is re-run in some environments
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False # Prevent root logger from also handling messages

# Paths
AUDIO_FOLDER = "audio_files"  # Folder to store downloaded audio
ANALYSIS_FOLDER = "analysis_results" # Folder to store analysis results
os.makedirs(AUDIO_FOLDER, exist_ok=True)  # Create the folder if it doesn't exist
os.makedirs(ANALYSIS_FOLDER, exist_ok=True) # Create the analysis folder

# Whisper model initialization
# Consider adding error handling for model loading
try:
    model = whisper.load_model("base")
    logger.info("Whisper model 'base' loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    logger.error("Ensure PyTorch is installed correctly for your system (CPU or GPU).")
    logger.error("If using GPU, check CUDA compatibility and drivers.")
    logger.error("Try installing the CPU-only version: pip install -U openai-whisper torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu")
    logger.error("Also ensure ffmpeg is installed and in your system's PATH.")
    exit(1) # Exit with a non-zero code to indicate error

# Deepseek API key - Hardcoded directly (Less secure)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# --- Function Definitions ---

def read_urls_from_file(file_name='urls3.txt'):
    """Reads URLs from a file and returns a list of URLs."""
    if not os.path.exists(file_name):
        logger.error(f"URL file not found: {file_name}")
        return []
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            urls = file.readlines()
        valid_urls = [url.strip() for url in urls if url.strip() and not url.strip().startswith('#')]
        logger.info(f"Read {len(valid_urls)} valid URLs from {file_name}")
        return valid_urls
    except Exception as e:
        logger.exception(f"Error reading URL file {file_name}: {e}")
        return []

def download_audio(url, output_folder):
    """Downloads an audio/video file from the given URL, generating a unique filename using a hash."""
    if not url.startswith(('http://', 'https://')):
        logger.warning(f"URL does not seem valid (missing http/https): {url}. Skipping download.")
        return None
    try:
        # --- Generate Unique Base Name ---
        # Create a unique identifier from the full URL
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16] # Use first 16 chars of MD5 hash

        # Try to get a 'hint' from the path for readability, default to 'recording'
        path_hint = "recording"
        try:
            parsed_url = urlparse(url)
            path_part = parsed_url.path.strip('/')
            if path_part:
                 # Get the last part of the path
                 base_hint = os.path.basename(path_part)
                 if base_hint and base_hint != '/':
                    # Sanitize hint
                    path_hint = re.sub(r'[^a-zA-Z0-9_-]+', '_', base_hint)
                    path_hint = re.sub(r'_+', '_', path_hint).strip('_')
                    path_hint = path_hint[:30] # Limit hint length
        except Exception as parse_err:
            logger.debug(f"Could not parse path hint from URL {url}: {parse_err}")

        # Combine hint and hash for a more readable unique name
        # Example: "recording-public_a1b2c3d4e5f6a7b8"
        file_base_name_unique = f"{path_hint}_{url_hash}"
        logger.debug(f"Generated unique base name: {file_base_name_unique} for URL: {url}")
        # --- End Unique Base Name ---

        # Use this unique base name for the rest of the process
        safe_file_name = file_base_name_unique

        # --- Extension Handling ---
        # Assume .mp3 by default for Ringba-like URLs or if extension is missing/invalid
        assumed_ext = ".mp3"
        final_extension = assumed_ext
        try:
             # Attempt to get extension from the original path *before* query string
             original_ext = os.path.splitext(os.path.basename(unquote(urlparse(url).path)))[1].lower()
             valid_exts = ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.mp4', '.mov', '.wmv', '.avi', '.mkv', '.webm')
             if original_ext and original_ext in valid_exts:
                 final_extension = original_ext
                 logger.debug(f"Using original extension '{final_extension}' from URL path.")
             elif original_ext:
                 logger.warning(f"Original extension '{original_ext}' not typical. Using {assumed_ext} for: {url}")
             else:
                 logger.info(f"No file extension found in path, assuming {assumed_ext} for: {url}")
        except Exception as ext_err:
             logger.error(f"Error extracting extension, defaulting to {assumed_ext}: {ext_err}")

        safe_file_name += final_extension
        # --- End Extension Handling ---

        # --- Final Sanitization and Path Creation ---
        # Sanitize the combined name (hash should be safe, but sanitize anyway)
        safe_file_name = re.sub(r'[\\/*?:"<>|]+', '_', safe_file_name)
        safe_file_name = re.sub(r'[^a-zA-Z0-9._-]+', '_', safe_file_name) # Allow dots, underscores, hyphens
        safe_file_name = re.sub(r'_+', '_', safe_file_name).strip('._')
        if not safe_file_name: # Fallback if sanitization removes everything
            safe_file_name = f"download_{url_hash}{final_extension}"

        # Max length check (optional now, but keep for safety)
        max_len = 150 # Increased max length slightly
        if len(safe_file_name) > max_len:
            name, ext = os.path.splitext(safe_file_name)
            ext = ext[:10] # Limit extension length just in case
            safe_file_name = name[:max_len - len(ext)] + ext

        audio_file_path = os.path.join(output_folder, safe_file_name)

        # Counter logic is now just a fallback for hash collisions or identical URLs in list
        counter = 1
        base_name_part, ext_part = os.path.splitext(safe_file_name)
        # Check existence *before* attempting download
        while os.path.exists(audio_file_path):
            logger.warning(f"Filename collision even with hashing! URL: {url}. Base: {base_name_part}. Trying counter.")
            audio_file_path = os.path.join(output_folder, f"{base_name_part}_{counter}{ext_part}")
            counter += 1
        if counter > 1:
            logger.info(f"Saving with counter as {os.path.basename(audio_file_path)} due to collision.")
        # --- End Sanitization ---

        # --- Download Process ---
        logger.info(f"Attempting to download: {url} to {audio_file_path}") # Log the final path
        with requests.Session() as session:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = session.get(url, timeout=60, stream=True, headers=headers, allow_redirects=True)
            response.raise_for_status() # Raise exception for bad status codes

            content_type = response.headers.get('Content-Type', '').lower()
            logger.debug(f"Content-Type: {content_type}")
            # Optional: Add more robust content-type check if needed

            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            chunk_size=8192
            logger.info(f"File size: {total_size / (1024*1024):.2f} MB" if total_size > 0 else "File size unknown")
            progress_log_interval = 5 * 1024 * 1024 # Log every 5MB

            with open(audio_file_path, 'wb') as f:
                last_logged_milestone = 0
                for chunk in response.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    if total_size > 0 and bytes_downloaded > progress_log_interval:
                         # Log progress percentage
                         percentage = bytes_downloaded * 100 / total_size
                         current_milestone = bytes_downloaded // progress_log_interval
                         if current_milestone > last_logged_milestone:
                              logger.info(f"Downloaded {bytes_downloaded / (1024*1024):.2f} / {total_size / (1024*1024):.2f} MB ({percentage:.1f}%)")
                              last_logged_milestone = current_milestone


            if total_size != 0 and bytes_downloaded != total_size:
                logger.warning(f"Downloaded size ({bytes_downloaded}) does not match expected size ({total_size}) for {audio_file_path}")

        logger.info(f"Successfully downloaded audio to {audio_file_path}")
        return audio_file_path
        # --- End Download Process ---

    # --- Error Handling ---
    except requests.exceptions.Timeout:
        logger.error(f"Timeout occurred while downloading: {url}")
        return None
    except requests.exceptions.RequestException as e:
        # Log more specific HTTP error if available
        status_code_info = ""
        if hasattr(e, 'response') and e.response is not None:
           status_code_info = f" (Status Code: {e.response.status_code})"
        logger.error(f"Failed to download audio from {url}: {e}{status_code_info}")
        return None
    except Exception as e:
        logger.exception(f"An unexpected error occurred during download for {url}: {e}")
        # Attempt to remove partial file on unexpected error
        if 'audio_file_path' in locals() and os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                logger.info(f"Removed partially downloaded file due to error: {audio_file_path}")
            except OSError as rm_err:
                logger.error(f"Could not remove partial file {audio_file_path}: {rm_err}")
        return None
    # --- End Error Handling ---

def transcribe_audio(file_path):
    """Transcribes audio using the loaded Whisper model."""
    if not file_path or not os.path.exists(file_path):
        logger.error(f"Audio file not found or path is invalid for transcription: {file_path}")
        return ""
    try:
        if os.path.getsize(file_path) == 0:
            logger.error(f"Audio file is empty, skipping transcription: {file_path}")
            return ""
    except OSError as e:
        logger.error(f"Could not get file size for {file_path}: {e}. Skipping transcription.")
        return ""

    logger.info(f"Starting transcription for: {file_path}")
    try:
        result = model.transcribe(file_path, fp16=False)
        transcript_text = result.get("text", "").strip()
        if not transcript_text:
             logger.warning(f"Transcription resulted in empty text for: {file_path}. Check audio content.")
        else:
             logger.info(f"Transcription successful for: {file_path}")
             logger.debug(f"Transcript snippet: {transcript_text[:150]}...")
        return transcript_text
    except Exception as e:
        logger.exception(f"Whisper transcription failed for {file_path}: {e}")
        if "ffmpeg" in str(e).lower():
             logger.error("This might be an issue with the ffmpeg installation or the audio file format/integrity.")
             logger.error("Ensure ffmpeg is installed and in your system's PATH.")
        if "cuda" in str(e).lower() or "cublas" in str(e).lower():
             logger.error("A CUDA-related error occurred. Check GPU memory, drivers, and PyTorch/CUDA compatibility.")
        if "memory" in str(e).lower():
             logger.error("An out-of-memory error occurred. Try a smaller Whisper model or process shorter audio segments if possible.")
        return ""

def analyze_transcript_with_llm(transcript, audio_filename):
    """Sends the transcript to Deepseek's API for analysis."""
    if not transcript:
        logger.warning(f"Skipping analysis for {audio_filename} due to empty transcript.")
        return "Analysis skipped: Empty transcript provided."
    if not DEEPSEEK_API_KEY or "YOUR_DEFAULT_KEY_HERE" in DEEPSEEK_API_KEY or len(DEEPSEEK_API_KEY) < 10:
         logger.error("Deepseek API key is not configured correctly or is invalid. Skipping analysis.")
         return "Analysis failed: Deepseek API key not set or invalid."

    logger.info(f"Sending transcript for analysis: {audio_filename} (length: {len(transcript)} chars)")
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # --- Define the dynamic birth date cutoff ---
        today = datetime.date.today()
        cutoff_date_str = "April 24, 1944" # Default fallback
        if dateutil_available:
            try:
                cutoff_date = today - relativedelta(years=81)
                cutoff_date_str = cutoff_date.strftime("%B %d, %Y")
                logger.info(f"Using age cutoff date (81+): Born on or before {cutoff_date_str}")
            except Exception as date_err:
                 logger.error(f"Error calculating cutoff date using dateutil: {date_err}. Using fixed placeholder.")
        else:
             logger.warning("python-dateutil library not found. Using approximate age cutoff calculation.")
             cutoff_year = today.year - 81
             cutoff_date_str = f"approximately before {today.strftime('%B %d')}, {cutoff_year}"

        # --- Updated Prompt ---
        # Instruct the LLM to ONLY return the structured data points.
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
    - Agent explicitly states submission of a NEW application during the call.
    - Requires collection of:
        - Portion of SSN (last 4, first 5, or full 9).
        - Checking/Savings account (Routing & Account #) OR Credit Card Number.
    - Confirmation details mentioned (one or more):
        - Acknowledgment of submission.
        - Policy effective dates.
        - Reference/Policy numbers.

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
Do NOT include any introductory sentences, concluding remarks, summaries (like "### Summary:"), markdown formatting (like '###' or '```'), or any text other than the requested fields and their values.
Ensure every field listed under 'Output for Billability', 'Output for Application Submission', 'Supporting Information', and 'Abrupt Ending Analysis' is present in your response, even if the value is 'No' or 'Not Provided'.
"""
        messages = [
            # System message can still be helpful for overall context
            {"role": "system", "content": "You are an AI assistant analyzing call transcripts. Provide ONLY the requested structured data."},
            {"role": "user", "content": prompt_content}
        ]

        data = {
            "messages": messages,
            "model": "deepseek-chat",
            "max_tokens": 1024, # Adjusted slightly, analysis output is structured and shorter now
            "temperature": 0.1,
            "stream": False,
        }

        # *** THIS LINE IS NOW CORRECT ***
        api_endpoint = "https://api.deepseek.com/v1/chat/completions"        
        # ********************************

        logger.debug(f"Sending request to Deepseek API. Endpoint: {api_endpoint}")
        response = requests.post(
            api_endpoint, # Use the corrected variable
            headers=headers,
            json=data,
            timeout=90
        )

        logger.debug(f"Received response from Deepseek API. Status code: {response.status_code}")
        response.raise_for_status()

        result = response.json()
        logger.debug(f"Deepseek API Response (usage): {result.get('usage')}")
        if "choices" in result and len(result["choices"]) > 0:
             logger.debug(f"Deepseek API Response (finish_reason): {result['choices'][0].get('finish_reason')}")

        if "choices" in result and len(result["choices"]) > 0 and "message" in result["choices"][0] and "content" in result["choices"][0]["message"]:
            analysis_content = result["choices"][0]["message"]["content"].strip()
            # Basic validation: Check if it starts roughly as expected
            if not analysis_content.startswith(("- Billable:", "Billable:")):
                 logger.warning(f"Analysis output for {audio_filename} does not start as expected. Content: {analysis_content[:100]}...")
            else:
                 logger.info(f"Analysis successful for: {audio_filename}")
            return analysis_content
        else:
            logger.error(f"Deepseek API response format unexpected or empty for {audio_filename}. Raw Response: {result}")
            return "Analysis failed: Unexpected API response format."

    except requests.exceptions.Timeout:
        logger.error(f"Deepseek API request timed out for {audio_filename}")
        return "Analysis failed: API request timed out"
    except requests.exceptions.HTTPError as http_err:
         logger.error(f"HTTP error occurred during Deepseek API call for {audio_filename}: {http_err}")
         error_message = f"Analysis failed: API Error {response.status_code}."
         try:
             error_details = response.json()
             logger.error(f"API Error Details: {error_details}")
             api_msg = error_details.get('error', {}).get('message', '')
             if api_msg:
                 error_message += f" Message: {api_msg}"
             else:
                 error_message += f" Response: {response.text[:500]}"
         except requests.exceptions.JSONDecodeError:
             logger.error(f"API Response Text (non-JSON): {response.text[:500]}")
             error_message += f" Check API key, endpoint, model name, and request format. Response: {response.text[:200]}"
         return error_message

    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request exception occurred during Deepseek API call for {audio_filename}: {req_err}")
        # Specifically check for InvalidSchema which was the previous error
        if isinstance(req_err, requests.exceptions.InvalidSchema):
             logger.error(f"InvalidSchema error: The URL '{api_endpoint}' is likely malformed.") # Log the URL being used
        return f"Analysis failed: Network or connection error ({type(req_err).__name__})"
    except Exception as e:
        logger.exception(f"An unexpected error occurred during LLM analysis for {audio_filename}: {e}")
        return f"Analysis failed: Unexpected error ({type(e).__name__})"

def save_analysis_to_file(analysis_content, base_filename, analysis_folder):
    """Saves the analysis content to a text file."""
    try:
        # Create filename like 'recording-public_4_analysis.txt'
        analysis_filename = f"{os.path.splitext(base_filename)[0]}_analysis.txt"
        analysis_filepath = os.path.join(analysis_folder, analysis_filename)

        with open(analysis_filepath, 'w', encoding='utf-8') as f:
            f.write(analysis_content)
        logger.info(f"Analysis saved to: {analysis_filepath}")
        return True
    except Exception as e:
        logger.exception(f"Failed to save analysis file for {base_filename}: {e}")
        return False

# --- Main Processing Logic ---

def process_single_call(url, audio_folder, analysis_folder):
    """Downloads, transcribes, analyzes, saves analysis, and cleans up audio."""
    logger.info(f"Processing URL: {url}")
    audio_file_path = None
    analysis_result = "Analysis not performed"
    transcript = ""
    status = "Started"

    try:
        # 1. Download
        audio_file_path = download_audio(url, audio_folder)
        if not audio_file_path:
            logger.error(f"Skipping further processing for URL due to download failure: {url}")
            analysis_result = "Analysis skipped: Download failed"
            status = "Download Failed"
        else:
            status = "Downloaded"
            audio_filename = os.path.basename(audio_file_path) # Get the actual filename used

            # 2. Transcribe
            transcript = transcribe_audio(audio_file_path)
            if not transcript:
                logger.error(f"Transcription failed or resulted in empty text for {audio_filename}. Skipping analysis.")
                analysis_result = "Analysis skipped: Transcription failed or empty"
                status = "Transcription Failed"
            else:
                status = "Transcribed"

                # 3. Analyze
                analysis_result = analyze_transcript_with_llm(transcript, audio_filename)
                if "Analysis failed" in analysis_result:
                    status = "Analysis Failed"
                    # Log the failure reason contained in analysis_result
                    logger.error(f"Analysis failed for {audio_filename}: {analysis_result}")
                elif "Analysis skipped" in analysis_result:
                     status = "Analysis Skipped" # Should not happen if transcript exists
                     logger.warning(f"Analysis skipped for {audio_filename} despite transcript existing.")
                else:
                     # 4. Save Analysis to File (only on success)
                     if save_analysis_to_file(analysis_result, audio_filename, analysis_folder):
                         status = "Analysis Success"
                     else:
                         status = "Save Analysis Failed"
                         # Log the raw analysis to console as a fallback if saving failed
                         logger.error(f"Failed to save analysis file, logging result for {audio_filename} here:\n{analysis_result}")

    except Exception as e:
        logger.exception(f"An critical unexpected error occurred processing URL {url}: {e}")
        analysis_result = f"Analysis failed: Critical error during processing ({type(e).__name__})"
        logger.error(analysis_result)
        status = "Critical Error"

    finally:
        # 5. Clean up downloaded audio file
        if audio_file_path and os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                logger.info(f"Cleaned up audio file: {audio_file_path}")
            except OSError as e:
                logger.error(f"Error removing audio file {audio_file_path}: {e}")
        else:
             if status not in ["Download Failed", "Started"]:
                 if not audio_file_path:
                     logger.debug(f"No audio file path available for {url}, skipping cleanup.")
                 elif audio_file_path:
                     logger.debug(f"Audio file {audio_file_path} not found for cleanup.")

        logger.info(f"Finished processing attempt for URL: {url}. Final Status: {status}")
        logger.info("-" * 70)
        return status

def process_all_calls(url_file='urls3.txt', audio_folder=AUDIO_FOLDER, analysis_folder=ANALYSIS_FOLDER):
    """Reads URLs, then processes each call individually and reports summary."""
    urls = read_urls_from_file(url_file)
    if not urls:
        logger.warning("No URLs found in the file or file couldn't be read. Exiting.")
        return

    total_urls = len(urls)
    logger.info(f"Starting processing for {total_urls} URLs from {url_file}...")
    logger.info(f"Analysis results will be saved in: {os.path.abspath(analysis_folder)}")

    status_counts = {
        "Analysis Success": 0,
        "Download Failed": 0,
        "Transcription Failed": 0,
        "Analysis Failed": 0,
        "Analysis Skipped": 0,
        "Save Analysis Failed": 0,
        "Critical Error": 0,
        "Started": 0, # Should ideally not be a final state
        "Unknown": 0
    }

    for i, url in enumerate(urls, 1):
        logger.info(f"--- Processing URL {i}/{total_urls} ---")
        final_status = "Unknown"
        try:
             # Pass the analysis folder path to the processing function
             final_status = process_single_call(url, audio_folder, analysis_folder)

        except Exception as loop_err:
             logger.error(f"A critical error occurred in the main loop for URL {url}, attempting to continue: {loop_err}")
             final_status = "Critical Error"

        # Use .get() with a default for safety in case an unexpected status string is returned
        status_counts[final_status] = status_counts.get(final_status, 0) + 1

    # Log Summary Report
    logger.info("=" * 70)
    logger.info("Processing Summary:")
    logger.info(f"Total URLs Attempted: {total_urls}")
    for status, count in status_counts.items():
         if count > 0:
             logger.info(f"- {status}: {count}")
    logger.info(f"Analysis results saved in: {os.path.abspath(analysis_folder)}")
    logger.info("=" * 70)

# --- Script Execution ---

if __name__ == "__main__":
    logger.info("Script started. Log file: %s", log_file)
    if not dateutil_available:
         logger.warning("python-dateutil library not found (pip install python-dateutil). Age calculation will be approximate.")

    # Ensure analysis folder exists before starting processing
    try:
        os.makedirs(ANALYSIS_FOLDER, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create analysis directory '{ANALYSIS_FOLDER}': {e}. Exiting.")
        exit(1)

    process_all_calls() # Use defaults

    logger.info("Script finished.")
