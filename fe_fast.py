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

# Try to import faster-whisper for SPEED
try:
    from faster_whisper import WhisperModel
    USE_FASTER_WHISPER = True
    print("✅ Using faster-whisper (4-10x faster transcription)")
except ImportError:
    import whisper
    USE_FASTER_WHISPER = False
    print("⚠️ Using regular whisper (slower). Install: pip install faster-whisper")

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
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(ANALYSIS_FOLDER, exist_ok=True)

# Initialize model
if USE_FASTER_WHISPER:
    try:
        model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=4)
        logger.info("Faster-Whisper 'tiny' model loaded for maximum speed")
    except Exception as e:
        logger.error(f"Failed to load Faster-Whisper: {e}")
        sys.exit(1)
else:
    try:
        model = whisper.load_model("base")
        logger.info("Whisper 'base' model loaded")
    except Exception as e:
        logger.error(f"Failed to load Whisper: {e}")
        sys.exit(1)

# Deepseek API key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

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
        if file_size > 20 * 1024 * 1024:  # 20MB
            logger.info(f"Compressing large file ({file_size/(1024*1024):.1f}MB)...")
            compressed = os.path.join(output_folder, f"compressed_{url_hash}.mp3")
            cmd = ['ffmpeg', '-i', audio_file, '-acodec', 'mp3', '-ab', '32k', 
                   '-ar', '16000', '-ac', '1', '-y', compressed]
            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=60)
                os.remove(audio_file)
                return compressed
            except:
                pass
        
        return audio_file
        
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None

def transcribe_audio_fast(file_path):
    """Fast transcription"""
    if not file_path or not os.path.exists(file_path):
        return ""
    
    logger.info(f"Transcribing: {os.path.basename(file_path)}")
    
    try:
        if USE_FASTER_WHISPER:
            segments_gen, info = model.transcribe(
                file_path,
                beam_size=1,
                language="en",
                vad_filter=True,
                condition_on_previous_text=False
            )
            
            text_parts = []
            for segment in segments_gen:
                text_parts.append(segment.text)
            
            transcript = " ".join(text_parts).strip()
        else:
            result = model.transcribe(file_path, language="en", fp16=False)
            transcript = result.get("text", "").strip()
        
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
    
    # YOUR EXACT PROMPT
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

def process_all_urls(urls):
    """Process each URL individually, collect all results"""
    all_results = []
    
    for i, url in enumerate(urls, 1):
        logger.info(f"\n[{i}/{len(urls)}] Processing: {url[:80]}...")
        
        result = {
            'url': url,
            'call_number': i,
            'status': 'Processing',
            'analysis': ''
        }
        
        # Download
        audio_file = download_audio_fast(url, AUDIO_FOLDER)
        if not audio_file:
            result['status'] = 'Download Failed'
            result['analysis'] = 'Analysis skipped: Download Failed'
            all_results.append(result)
            continue
        
        # Transcribe
        transcript = transcribe_audio_fast(audio_file)
        
        # Clean up audio immediately
        try:
            os.remove(audio_file)
            logger.info("Cleaned up audio file")
        except:
            pass
        
        if not transcript:
            result['status'] = 'Transcription Failed'
            result['analysis'] = 'Analysis skipped: No Transcript'
            all_results.append(result)
            continue
        
        # Analyze THIS SPECIFIC TRANSCRIPT
        analysis = analyze_single_transcript(transcript, url)
        result['status'] = 'Success'
        result['analysis'] = analysis
        all_results.append(result)
        
        # Clear memory
        gc.collect()
        
        logger.info(f"Completed call {i}")
    
    return all_results

def save_combined_output(results):
    """Save ALL results to ONE file"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(ANALYSIS_FOLDER, f"combined_analysis_{timestamp}.txt")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("COMBINED CALL ANALYSIS REPORT\n")
        f.write(f"Generated: {datetime.datetime.now()}\n")
        f.write(f"Total Calls: {len(results)}\n")
        f.write("="*80 + "\n\n")
        
        # Summary
        success = sum(1 for r in results if r['status'] == 'Success')
        failed = len(results) - success
        f.write(f"Successfully Analyzed: {success}\n")
        f.write(f"Failed: {failed}\n")
        f.write("\n" + "="*80 + "\n\n")
        
        # Individual results
        for result in results:
            f.write(f"--- CALL {result['call_number']} ---\n")
            f.write(f"URL: {result['url']}\n")
            f.write(f"Status: {result['status']}\n")
            f.write("\nANALYSIS:\n")
            f.write(result['analysis'])
            f.write("\n\n" + "-"*60 + "\n\n")
    
    logger.info(f"\n✅ All results saved to: {output_file}")
    return output_file

# --- MAIN ---
if __name__ == "__main__":
    logger.info("🚀 Fast Call Analysis Script Started")
    
    # Read URLs
    urls = read_urls_from_file('urls.txt')
    if not urls:
        logger.error("No URLs found")
        sys.exit(1)
    
    # Process each URL individually
    start_time = datetime.datetime.now()
    results = process_all_urls(urls)
    
    # Save everything to ONE file
    output_file = save_combined_output(results)
    
    # Summary
    duration = (datetime.datetime.now() - start_time).total_seconds()
    logger.info("\n" + "="*70)
    logger.info(f"✅ PROCESSING COMPLETE")
    logger.info(f"Total URLs: {len(urls)}")
    logger.info(f"Time: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    logger.info(f"Output: {output_file}")
    logger.info("="*70)
