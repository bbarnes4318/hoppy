# Import libraries
import os
import sys
import logging
import requests
import datetime
import re
import hashlib
import gc
import subprocess
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
import torch
import whisperx

# Load environment variables
load_dotenv()

# Check dateutil
try:
    from dateutil.relativedelta import relativedelta
    dateutil_available = True
except ImportError:
    dateutil_available = False

# Set up logging
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
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

# Paths
AUDIO_FOLDER = "audio_files"
ANALYSIS_FOLDER = "analysis_results"
TRANSCRIPTS_FOLDER = "transcripts"
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(ANALYSIS_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)

# API keys
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# Initialize WhisperX
device = "cpu"
compute_type = "int8"
batch_size = 8

logger.info("Loading WhisperX model...")
try:
    whisper_model = whisperx.load_model("tiny", device, compute_type=compute_type)
    logger.info("✅ WhisperX model loaded")
except Exception as e:
    logger.error(f"Failed to load WhisperX: {e}")
    sys.exit(1)

# Load alignment model (will be loaded when needed)
align_model = None
align_metadata = None

# Load diarization pipeline (robust across whisperx versions)
diarization_available = False
diarize_model = None
if HF_TOKEN:
    try:
        logger.info("Loading speaker diarization model...")
        try:
            # Preferred modern location
            from whisperx.diarize import DiarizationPipeline
            diarize_model = DiarizationPipeline(use_auth_token=HF_TOKEN, device=device)
        except Exception:
            # Fall back to any exposed helpers on the module
            if hasattr(whisperx, "DiarizationPipeline"):
                diarize_model = whisperx.DiarizationPipeline(use_auth_token=HF_TOKEN, device=device)
            elif hasattr(whisperx, "load_diarize_model"):
                diarize_model = whisperx.load_diarize_model(use_auth_token=HF_TOKEN, device=device)
            else:
                raise AttributeError("No diarization pipeline available in this whisperx version.")
        diarization_available = True
        logger.info("✅ Speaker diarization loaded")
    except Exception as e:
        logger.warning(f"⚠️ Diarization failed to load: {e}")
        logger.warning("Continuing without speaker labels")
else:
    logger.warning("⚠️ No HUGGINGFACE_TOKEN - speaker diarization disabled")

def read_urls_from_file(file_name='urls.txt'):
    """Read URLs from file"""
    if not os.path.exists(file_name):
        logger.error(f"URL file not found: {file_name}")
        return []
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            urls = [url.strip() for url in file if url.strip() and not url.strip().startswith('#')]
        logger.info(f"Loaded {len(urls)} URLs from {file_name}")
        return urls
    except Exception as e:
        logger.error(f"Error reading URLs: {e}")
        return []

def download_audio_fast(url, output_folder):
    """Download and optionally compress audio"""
    if not url.startswith(('http://', 'https://')):
        return None

    try:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        audio_file = os.path.join(output_folder, f"audio_{url_hash}.mp3")

        logger.info(f"Downloading: {url}")

        response = requests.get(url, stream=True, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()

        with open(audio_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Compress if large
        file_size = os.path.getsize(audio_file)
        if file_size > 20 * 1024 * 1024:
            logger.info(f"Compressing large file ({file_size/(1024*1024):.1f}MB)...")
            compressed = os.path.join(output_folder, f"compressed_{url_hash}.mp3")
            cmd = ['ffmpeg', '-i', audio_file, '-acodec', 'mp3',
                   '-ab', '32k', '-ar', '16000', '-ac', '1', '-y', compressed]
            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=60)
                os.remove(audio_file)
                return compressed
            except Exception:
                # If compression fails, keep original
                pass

        return audio_file

    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None

def transcribe_with_speakers(audio_file):
    """Transcribe with WhisperX and add speaker diarization"""
    global align_model, align_metadata

    if not audio_file or not os.path.exists(audio_file):
        return ""

    logger.info(f"Transcribing: {os.path.basename(audio_file)}")

    try:
        # Load audio
        audio = whisperx.load_audio(audio_file)

        # Step 1: Transcribe with WhisperX
        logger.info("Transcribing audio with WhisperX...")
        result = whisper_model.transcribe(audio, batch_size=batch_size)

        # Step 2: Align whisper output
        logger.info("Aligning transcript...")
        language = result["language"]

        # Load alignment model if not loaded
        if align_model is None:
            align_model, align_metadata = whisperx.load_align_model(
                language_code=language,
                device=device
            )

        result = whisperx.align(
            result["segments"],
            align_model,
            align_metadata,
            audio,
            device,
            return_char_alignments=False
        )

        # Step 3: Assign speakers (if available)
        if diarization_available and diarize_model:
            logger.info("Performing speaker diarization...")
            diarize_segments = diarize_model(audio)
            # Depending on whisperx version, the function signature may vary.
            # This is the common variant:
            result = whisperx.assign_word_speakers(diarize_segments, result)
            logger.info("✅ Speaker diarization complete")

        # Step 4: Build transcript with speaker labels
        transcript_parts = []
        current_speaker = None

        for segment in result["segments"]:
            speaker = segment.get("speaker", "SPEAKER_UNKNOWN")

            # Add speaker label when speaker changes
            if speaker != current_speaker:
                transcript_parts.append(f"\n[{speaker}]: ")
                current_speaker = speaker

            transcript_parts.append(segment["text"])

        transcript = "".join(transcript_parts).strip()
        logger.info(f"Transcription complete: {len(transcript)} chars")
        return transcript

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return ""

def analyze_single_transcript(transcript, url_identifier):
    """Analyze ONE transcript with YOUR EXACT PROMPT"""
    if not transcript:
        return "Analysis skipped: Empty transcript"
    if not DEEPSEEK_API_KEY:
        return "Analysis failed: No API key"

    logger.info(f"Analyzing transcript for: {url_identifier[:60]}...")

    # Calculate age cutoff
    today = datetime.date.today()
    if dateutil_available:
        cutoff_date = today - relativedelta(years=81)
        cutoff_date_str = cutoff_date.strftime("%B %d, %Y")
    else:
        cutoff_year = today.year - 81
        cutoff_date_str = f"{today.strftime('%B %d')}, {cutoff_year}"

    # PROMPT
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
Do NOT include any introductory sentences, concluding remarks, summaries (like "### Summary:"), markdown formatting (like '###' or '```'), or any text other than the requested fields and their values.
Ensure every field listed under 'Output for Billability', 'Output for Application Submission', 'Supporting Information', and 'Abrupt Ending Analysis' is present in your response, even if the value is 'No' or 'Not Provided'.
"""

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        messages = [
            {"role": "system", "content": "You are an AI assistant analyzing call transcripts. Provide ONLY the requested structured data."},
            {"role": "user", "content": prompt_content}
        ]

        data = {
            "messages": messages,
            "model": "deepseek-chat",
            "max_tokens": 1024,
            "temperature": 0.1,
            "stream": False
        }

        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=90
        )
        response.raise_for_status()

        result = response.json()
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"].strip()
        return "Analysis failed: No response"

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return f"Analysis failed: {str(e)}"

def extract_application_status(analysis_text):
    """Extract whether application was submitted from analysis"""
    try:
        match = re.search(r'Application Submitted:\s*(Yes|No)', analysis_text, re.IGNORECASE)
        if match:
            return match.group(1).lower() == 'yes'
        return False
    except Exception:
        return False

def process_all_urls(urls):
    """Process each URL individually, collect all results"""
    all_results = []

    for i, url in enumerate(urls, 1):
        logger.info(f"\n[{i}/{len(urls)}] Processing: {url[:80]}...")

        result = {
            'url': url,
            'call_number': i,
            'status': 'Processing',
            'transcript': '',
            'analysis': '',
            'application_submitted': False
        }

        # Download
        audio_file = download_audio_fast(url, AUDIO_FOLDER)
        if not audio_file:
            result['status'] = 'Download Failed'
            result['analysis'] = 'Analysis skipped: Download Failed'
            all_results.append(result)
            continue

        # Transcribe
        transcript = transcribe_with_speakers(audio_file)
        result['transcript'] = transcript

        # Clean up audio
        try:
            os.remove(audio_file)
            logger.info("Cleaned up audio file")
        except Exception:
            pass

        if not transcript:
            result['status'] = 'Transcription Failed'
            result['analysis'] = 'Analysis skipped: No Transcript'
            all_results.append(result)
            continue

        # Analyze
        analysis = analyze_single_transcript(transcript, url)
        result['status'] = 'Success'
        result['analysis'] = analysis
        result['application_submitted'] = extract_application_status(analysis)
        all_results.append(result)

        # Free memory
        gc.collect()
        logger.info(f"✅ Completed call {i}")

    return all_results

def save_separated_outputs(results):
    """Save transcripts and analyses separated by application status"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # File paths (APPEND mode)
    app_submitted_transcripts = os.path.join(TRANSCRIPTS_FOLDER, "applications_submitted_transcripts.txt")
    app_not_submitted_transcripts = os.path.join(TRANSCRIPTS_FOLDER, "applications_not_submitted_transcripts.txt")
    app_submitted_analysis = os.path.join(ANALYSIS_FOLDER, "applications_submitted_analysis.txt")
    app_not_submitted_analysis = os.path.join(ANALYSIS_FOLDER, "applications_not_submitted_analysis.txt")

    # Counters
    app_yes_count = sum(1 for r in results if r['application_submitted'] and r['status'] == 'Success')
    app_no_count = sum(1 for r in results if not r['application_submitted'] and r['status'] == 'Success')

    # Write transcripts - Application Submitted
    with open(app_submitted_transcripts, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"SESSION: {timestamp}\n")
        f.write(f"{'='*80}\n\n")
        for result in results:
            if result['application_submitted'] and result['status'] == 'Success':
                f.write(f"--- CALL {result['call_number']} (Application Submitted: YES) ---\n")
                f.write(f"URL: {result['url']}\n")
                f.write(f"Timestamp: {timestamp}\n\n")
                f.write("TRANSCRIPT (WITH SPEAKER LABELS):\n")
                f.write(result['transcript'])
                f.write("\n\n" + "-"*60 + "\n\n")

    # Write transcripts - Application NOT Submitted
    with open(app_not_submitted_transcripts, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"SESSION: {timestamp}\n")
        f.write(f"{'='*80}\n\n")
        for result in results:
            if not result['application_submitted'] and result['status'] == 'Success':
                f.write(f"--- CALL {result['call_number']} (Application Submitted: NO) ---\n")
                f.write(f"URL: {result['url']}\n")
                f.write(f"Timestamp: {timestamp}\n\n")
                f.write("TRANSCRIPT (WITH SPEAKER LABELS):\n")
                f.write(result['transcript'])
                f.write("\n\n" + "-"*60 + "\n\n")

    # Write analysis - Application Submitted
    with open(app_submitted_analysis, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"SESSION: {timestamp}\n")
        f.write(f"{'='*80}\n\n")
        for result in results:
            if result['application_submitted'] and result['status'] == 'Success':
                f.write(f"--- CALL {result['call_number']} (Application Submitted: YES) ---\n")
                f.write(f"URL: {result['url']}\n")
                f.write(f"Timestamp: {timestamp}\n\n")
                f.write("ANALYSIS:\n")
                f.write(result['analysis'])
                f.write("\n\n" + "-"*60 + "\n\n")

    # Write analysis - Application NOT Submitted
    with open(app_not_submitted_analysis, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"SESSION: {timestamp}\n")
        f.write(f"{'='*80}\n\n")
        for result in results:
            if not result['application_submitted'] and result['status'] == 'Success':
                f.write(f"--- CALL {result['call_number']} (Application Submitted: NO) ---\n")
                f.write(f"URL: {result['url']}\n")
                f.write(f"Timestamp: {timestamp}\n\n")
                f.write("ANALYSIS:\n")
                f.write(result['analysis'])
                f.write("\n\n" + "-"*60 + "\n\n")

    logger.info(f"\n✅ Files saved successfully!")
    logger.info(f"   Applications Submitted (YES): {app_yes_count} calls")
    logger.info(f"   - Transcripts: {app_submitted_transcripts}")
    logger.info(f"   - Analysis: {app_submitted_analysis}")
    logger.info(f"\n   Applications NOT Submitted (NO): {app_no_count} calls")
    logger.info(f"   - Transcripts: {app_not_submitted_transcripts}")
    logger.info(f"   - Analysis: {app_not_submitted_analysis}")

    return {
        'app_yes': app_yes_count,
        'app_no': app_no_count,
        'files': {
            'transcripts_yes': app_submitted_transcripts,
            'transcripts_no': app_not_submitted_transcripts,
            'analysis_yes': app_submitted_analysis,
            'analysis_no': app_not_submitted_analysis
        }
    }

if __name__ == "__main__":
    logger.info("🚀 WhisperX Call Analysis with Speaker Identification Started")

    if not diarization_available:
        logger.warning("⚠️ Running WITHOUT speaker identification")

    # Read URLs
    urls = read_urls_from_file('urls.txt')
    if not urls:
        logger.error("No URLs found")
        sys.exit(1)

    # Process each URL individually
    start_time = datetime.datetime.now()
    results = process_all_urls(urls)

    # Save to separated files
    output_info = save_separated_outputs(results)

    # Summary
    duration = (datetime.datetime.now() - start_time).total_seconds()
    logger.info("\n" + "="*70)
    logger.info(f"✅ PROCESSING COMPLETE")
    logger.info(f"Total URLs: {len(urls)}")
    logger.info(f"Time: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    logger.info(f"Applications Submitted: {output_info['app_yes']}")
    logger.info(f"Applications NOT Submitted: {output_info['app_no']}")
    logger.info("="*70)
