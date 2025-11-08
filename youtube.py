# Import libraries
import os
import sys
import logging
import requests
import datetime
import re
import hashlib
import subprocess
import json
import gc
from urllib.parse import urlparse, unquote, parse_qs
from dotenv import load_dotenv
import subprocess  # Add this for running yt-dlp

def check_yt_dlp_available():
    """Check if yt-dlp is installed"""
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False

def download_youtube_as_audio(url, output_folder, audio_format='mp3'):
    """
    Download YouTube video and convert to MP3 or WAV
    audio_format: 'mp3' or 'wav'
    """
    if not check_yt_dlp_available():
        logger.error("yt-dlp is not installed! Install with: pip install yt-dlp")
        logger.error("Also ensure ffmpeg is installed: https://ffmpeg.org/download.html")
        return None
    
    try:
        # Generate unique filename using URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        output_filename = f"youtube_{url_hash}.{audio_format}"
        output_path = os.path.join(output_folder, output_filename)
        
        # Build yt-dlp command
        cmd = [
            'yt-dlp',
            '-x',  # Extract audio only (no video)
            '--audio-format', audio_format,  # Convert to specified format
            '--audio-quality', '0' if audio_format == 'wav' else '128K',  # Best quality for WAV, 128K for MP3
            '-o', output_path,  # Output path
            '--no-playlist',  # Don't download playlists
            '--quiet',  # Less output
            '--no-warnings',
            url
        ]
        
        logger.info(f"Downloading YouTube audio as {audio_format.upper()}: {url}")
        logger.info(f"This may take a moment...")
        
        # Run yt-dlp
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.error(f"yt-dlp failed: {result.stderr}")
            return None
        
        # yt-dlp might add its own extension, so check for the file
        for file in os.listdir(output_folder):
            if file.startswith(f"youtube_{url_hash}"):
                actual_path = os.path.join(output_folder, file)
                logger.info(f"✅ Successfully downloaded YouTube audio to: {actual_path}")
                file_size_mb = os.path.getsize(actual_path) / (1024 * 1024)
                logger.info(f"File size: {file_size_mb:.2f} MB")
                return actual_path
        
        logger.error("Download appeared to succeed but file not found")
        return None
        
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout downloading YouTube video (took longer than 5 minutes): {url}")
        return None
    except Exception as e:
        logger.error(f"Error downloading YouTube audio: {e}")
        return None

# ADD THESE NEW IMPORTS FOR SPEAKER IDENTIFICATION
try:
    from pyannote.audio import Pipeline
    SPEAKER_DIARIZATION_AVAILABLE = True
    print("✅ Speaker diarization available")
except ImportError:
    SPEAKER_DIARIZATION_AVAILABLE = False
    print("⚠️ Install pyannote for speaker identification: pip install pyannote.audio")

def preprocess_large_file(file_path, max_size_mb=50):
    """Split or compress large files before processing"""
    import subprocess
    
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb <= max_size_mb:
        return [file_path]  # File is small enough
    
    logger.info(f"File too large ({file_size_mb:.1f} MB). Splitting into smaller parts...")
    
    base_name = os.path.splitext(file_path)[0]
    output_pattern = f"{base_name}_part_%03d.mp3"
    
    # Convert to audio-only MP3 and split into 10-minute segments
    cmd = [
        'ffmpeg', '-i', file_path,
        '-vn',  # No video
        '-acodec', 'mp3',
        '-ab', '64k',  # Lower bitrate
        '-ar', '16000',  # 16kHz sample rate
        '-f', 'segment',
        '-segment_time', '600',  # 10 minutes
        output_pattern
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Find all created parts
        parts = []
        for i in range(100):  # Max 100 parts
            part_file = f"{base_name}_part_{i:03d}.mp3"
            if os.path.exists(part_file):
                parts.append(part_file)
            else:
                break
        
        logger.info(f"Split into {len(parts)} parts")
        return parts
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to split file: {e}")
        return None

# Try to import faster-whisper, fall back to regular whisper
USE_FASTER_WHISPER = False
try:
    from faster_whisper import WhisperModel
    USE_FASTER_WHISPER = True
    print("✅ Using faster-whisper (4-10x faster transcription)")
except ImportError:
    import whisper
    print("⚠️ faster-whisper not found. Using regular whisper (slower).")
    print("💡 Install faster-whisper for 4-10x speed: pip install faster-whisper")

# Load environment variables
load_dotenv()

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
TRANSCRIPTS_FOLDER = "transcripts"       # Where full transcripts are saved
SUMMARIES_FOLDER = "summaries"           # Where summaries with timelines are saved
os.makedirs(INPUT_AUDIO_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)
os.makedirs(SUMMARIES_FOLDER, exist_ok=True)
YOUTUBE_FOLDER = "youtube_downloads"
ANALYSIS_FOLDER = "analysis_results"
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)  # Create YouTube folder
os.makedirs(ANALYSIS_FOLDER, exist_ok=True)

# Recognized audio/video extensions
AUDIO_EXTS = ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.mp4', '.mov', '.wmv', '.avi', '.mkv', '.webm')

# Speed settings for faster-whisper
SPEED_MODE = "balanced"  # Options: "fast", "balanced", "accurate"

# MEMORY SETTINGS - IMPORTANT FOR LARGE FILES
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB - files larger than this use special handling
CHUNK_LENGTH = 30  # Process audio in 30-second chunks for large files

SPEED_CONFIGS = {
    "fast": {
        "model_size": "tiny",
        "beam_size": 1,
        "vad_filter": True,
        "condition_on_previous_text": False  # Saves memory
    },
    "balanced": {
        "model_size": "base",
        "beam_size": 2,  # Reduced from 3
        "vad_filter": True,
        "condition_on_previous_text": False
    },
    "accurate": {
        "model_size": "small",
        "beam_size": 5,
        "vad_filter": False,
        "condition_on_previous_text": True
    }
}

def is_url(s: str) -> bool:
    return isinstance(s, str) and s.strip().lower().startswith(('http://', 'https://'))

# Initialize the transcription model
if USE_FASTER_WHISPER:
    try:
        config = SPEED_CONFIGS[SPEED_MODE]
        # Check for GPU
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
        except ImportError:
            device = "cpu"
            compute_type = "int8"
        
        if device == "cuda":
            logger.info(f"🚀 GPU detected! Using CUDA for 10x faster transcription")
        
        # For large files or low memory, force tiny model
        if os.environ.get("FORCE_TINY_MODEL", "").lower() == "true":
            config["model_size"] = "tiny"
            logger.info("Forcing tiny model for memory efficiency")
        
        model = WhisperModel(
            config["model_size"],
            device=device,
            compute_type=compute_type,
            cpu_threads=min(os.cpu_count() or 4, 4)  # Limit threads to save memory
        )
        logger.info(f"Faster-Whisper model '{config['model_size']}' loaded ({SPEED_MODE} mode)")
    except Exception as e:
        logger.error(f"Failed to load Faster-Whisper model: {e}")
        sys.exit(1)
else:
    try:
        model = whisper.load_model("base")
        logger.info("Whisper model 'base' loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        logger.error("Ensure PyTorch and ffmpeg are installed and configured.")
        sys.exit(1)

# Deepseek API key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Hugging Face token for speaker diarization (get from https://huggingface.co/settings/tokens)
HF_TOKEN = os.getenv("HF_TOKEN")

# Initialize speaker diarization pipeline
diarization_pipeline = None
if SPEAKER_DIARIZATION_AVAILABLE and HF_TOKEN:
    try:
        diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=HF_TOKEN
        )
        logger.info("Speaker diarization pipeline loaded")
    except Exception as e:
        logger.error(f"Failed to load diarization: {e}")
        logger.info("Get token from https://huggingface.co/settings/tokens")

# --- Helper Functions ---

def read_urls_from_file(file_name='urls.txt'):
    """Read URLs from text file"""
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

def format_timestamp(seconds):
    """Convert seconds to readable timestamp format (HH:MM:SS or MM:SS)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def check_yt_dlp_available():
    """Check if yt-dlp is available"""
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False

def convert_google_drive_url(url):
    """Convert Google Drive sharing URL to direct download URL"""
    patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1)
            direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            logger.info(f"Converted Google Drive URL to direct download: {direct_url}")
            return direct_url
    
    return url

def download_with_yt_dlp(url, output_folder):
    """Download video using yt-dlp (for YouTube and other supported sites)"""
    try:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        output_template = os.path.join(output_folder, f'video_{url_hash}.%(ext)s')
        
        cmd = [
            'yt-dlp',
            '-o', output_template,
            '--no-playlist',
            '--format', 'best[ext=mp4]/best',
            '--quiet',
            '--no-warnings',
            url
        ]
        
        logger.info(f"Downloading with yt-dlp: {url}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.error(f"yt-dlp failed: {result.stderr}")
            return None
        
        # Find the downloaded file
        for file in os.listdir(output_folder):
            if file.startswith(f'video_{url_hash}'):
                downloaded_path = os.path.join(output_folder, file)
                logger.info(f"Downloaded with yt-dlp to: {downloaded_path}")
                return downloaded_path
        
        logger.error("yt-dlp download completed but file not found")
        return None
        
    except subprocess.TimeoutExpired:
        logger.error(f"yt-dlp timeout for URL: {url}")
        return None
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None

# --- Core Download Function ---

def download_audio(url, output_folder):
    """Downloads an audio/video file from URL, with YouTube support"""
    if not url.startswith(('http://', 'https://')):
        logger.warning(f"URL does not seem valid (missing http/https): {url}. Skipping download.")
        return None
    
    # CHECK FOR YOUTUBE URLs
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com']
    is_youtube = any(domain in url.lower() for domain in youtube_domains)
    
    if is_youtube:
        logger.info("YouTube URL detected - will extract audio")
        # You can change 'mp3' to 'wav' here if you prefer WAV format
        # WAV files are larger but uncompressed
        return download_youtube_as_audio(url, output_folder, audio_format='mp3')
    
    # Convert Google Drive URLs
    if 'drive.google.com' in url:
        url = convert_google_drive_url(url)
    
    try:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        path_hint = "video"
        
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
        
        assumed_ext = ".mp4"
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
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            
            response = session.get(url, timeout=60, stream=True, headers=headers, allow_redirects=True)
            response.raise_for_status()
            
            # Check if we got an HTML page instead of a file
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type and 'drive.google.com' in url:
                logger.error(f"Received HTML instead of file from Google Drive. The file may be too large or require authentication.")
                logger.info("For Google Drive files, consider:")
                logger.info("1. Making the file publicly accessible")
                logger.info("2. Using a smaller file")
                logger.info("3. Downloading manually and placing in 'input_audio' folder")
                return None

            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            chunk_size = 8192
            
            with open(audio_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Progress indicator for large files
                        if total_size > 0 and bytes_downloaded % (chunk_size * 100) == 0:
                            progress = (bytes_downloaded / total_size) * 100
                            logger.info(f"Download progress: {progress:.1f}%")

            if total_size != 0 and bytes_downloaded != total_size:
                logger.warning(f"Downloaded size mismatch for {audio_file_path}")
            
            # Validate the downloaded file
            if bytes_downloaded < 1000:
                logger.error(f"Downloaded file is too small ({bytes_downloaded} bytes), likely not a valid media file")
                os.remove(audio_file_path)
                return None
            
            # Check if file is actually a media file
            with open(audio_file_path, 'rb') as f:
                header = f.read(16)
                
            media_signatures = [
                b'RIFF',  # WAV
                b'\x00\x00\x00\x18ftypmp4',  # MP4
                b'\x00\x00\x00 ftypM4A',  # M4A
                b'ID3',  # MP3
                b'\xFF\xFB',  # MP3
                b'OggS',  # OGG
                b'fLaC',  # FLAC
                b'\x1A\x45\xDF\xA3',  # MKV/WebM
            ]
            
            is_media = any(header.startswith(sig) or sig in header for sig in media_signatures)
            
            if not is_media and (b'<!DOCTYPE' in header or b'<html' in header):
                logger.error(f"Downloaded file appears to be HTML, not a media file")
                os.remove(audio_file_path)
                return None

        logger.info(f"Successfully downloaded to {audio_file_path}")
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
                logger.info(f"Removed partial/invalid file: {audio_file_path}")
            except OSError:
                pass
        return None

# --- Transcription Function with Memory Management ---

def transcribe_audio_with_timestamps(file_path):
    """Transcribe audio/video with memory-efficient chunk processing for large files"""
    global model  # MUST BE AT THE TOP OF THE FUNCTION - BEFORE ANY USE OF 'model'
    
    if not file_path or not os.path.exists(file_path):
        logger.error(f"File not found for transcription: {file_path}")
        return None, None
    
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.error(f"File is empty, skipping: {file_path}")
            return None, None
        
        file_size_mb = file_size / (1024 * 1024)
        logger.info(f"File size: {file_size_mb:.1f} MB")
        
        # Determine if we need special handling for large files
        use_chunking = file_size > LARGE_FILE_THRESHOLD
        
        if use_chunking:
            logger.warning(f"Large file detected ({file_size_mb:.1f} MB). Using memory-efficient chunk processing...")
            logger.info("This will take longer but won't run out of memory.")
        
    except OSError as e:
        logger.error(f"Could not get size for {file_path}: {e}")
        return None, None
    
    logger.info(f"Transcribing with timestamps: {file_path}")
    start_time = datetime.datetime.now()
    
    try:
        if USE_FASTER_WHISPER:
            config = SPEED_CONFIGS[SPEED_MODE]
            
            # For very large files, use more aggressive settings
            if use_chunking:
                # Override settings for memory efficiency
                vad_params = {
                    "threshold": 0.5,
                    "min_silence_duration_ms": 1000,  # Skip longer silences
                    "speech_pad_ms": 400
                }
                
                try:
                    logger.info("Processing in chunks to save memory...")
                    segments_gen, info = model.transcribe(
                        file_path,
                        beam_size=1,  # Minimal beam size
                        best_of=1,  # Don't generate multiple candidates
                        language="en",
                        vad_filter=True,  # Always use VAD for large files
                        vad_parameters=vad_params,
                        condition_on_previous_text=False,  # Save memory
                        chunk_length=CHUNK_LENGTH,  # Process in chunks
                        initial_prompt=None,
                        temperature=0,
                        compression_ratio_threshold=2.4,
                        log_prob_threshold=-1.0,
                        no_speech_threshold=0.6
                    )
                    
                    # Process segments with periodic garbage collection
                    segments = []
                    full_text_parts = []
                    segment_count = 0
                    
                    for segment in segments_gen:
                        segments.append({
                            'start': segment.start,
                            'end': segment.end,
                            'text': segment.text
                        })
                        full_text_parts.append(segment.text)
                        segment_count += 1
                        
                        # Periodic cleanup for memory
                        if segment_count % 100 == 0:
                            gc.collect()
                            logger.info(f"Processed {segment_count} segments...")
                    
                    full_transcript = " ".join(full_text_parts).strip()
                    
                except Exception as mem_error:
                    logger.error(f"Memory error: {mem_error}. Trying with tiny model...")
                    # Fallback to tiny model
                    # global model is already declared at top of function
                    del model
                    gc.collect()
                    
                    model = WhisperModel(
                        "tiny",
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=2
                    )
                    logger.info("Loaded tiny model for emergency processing")
                    
                    segments_gen, info = model.transcribe(
                        file_path,
                        beam_size=1,
                        language="en",
                        vad_filter=True,
                        chunk_length=15  # Even smaller chunks
                    )
                    
                    segments = []
                    full_text_parts = []
                    
                    for segment in segments_gen:
                        segments.append({
                            'start': segment.start,
                            'end': segment.end,
                            'text': segment.text
                        })
                        full_text_parts.append(segment.text)
                    
                    full_transcript = " ".join(full_text_parts).strip()
                    
            else:
                # Normal processing for smaller files
                segments_gen, info = model.transcribe(
                    file_path,
                    beam_size=config["beam_size"],
                    language="en",
                    vad_filter=config["vad_filter"],
                    vad_parameters=dict(min_silence_duration_ms=500) if config["vad_filter"] else None,
                    condition_on_previous_text=config.get("condition_on_previous_text", False)
                )
                
                segments = []
                full_text_parts = []
                
                for segment in segments_gen:
                    segments.append({
                        'start': segment.start,
                        'end': segment.end,
                        'text': segment.text
                    })
                    full_text_parts.append(segment.text)
                
                full_transcript = " ".join(full_text_parts).strip()
            
            # Log speed
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            if hasattr(info, 'duration'):
                speed_ratio = info.duration / elapsed if elapsed > 0 else 0
                logger.info(f"✅ Transcription complete in {elapsed:.1f}s (Speed: {speed_ratio:.1f}x realtime)")
            else:
                logger.info(f"✅ Transcription complete in {elapsed:.1f}s")
                
        else:
            # Regular whisper for large files - NOT RECOMMENDED
            if use_chunking:
                logger.error("Regular whisper doesn't support chunk processing well. Install faster-whisper!")
                logger.info("Attempting full file processing (may run out of memory)...")
            
            result = model.transcribe(file_path, fp16=False, verbose=False, language="en")
            full_transcript = result.get("text", "").strip()
            segments = result.get("segments", [])
            
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            logger.info(f"Transcription complete in {elapsed:.1f}s")
        
        if not full_transcript:  # ← FIXED: Moved left to align properly
            logger.warning(f"Empty transcript for: {file_path}")
            return None, None
        else:
            logger.info(f"Transcription successful: {len(full_transcript)} characters, {len(segments)} segments")

        # ============ ADD SPEAKER IDENTIFICATION HERE ============
        # Check if speaker diarization is available
        if diarization_pipeline and SPEAKER_DIARIZATION_AVAILABLE:
            try:
                logger.info("Identifying speakers in the audio...")
                diarization = diarization_pipeline(file_path)
                
                # Process each segment to assign speakers
                for segment in segments:
                    segment_mid = (segment['start'] + segment['end']) / 2
                    
                    # Find which speaker this segment belongs to
                    speaker_found = False
                    for turn, _, speaker in diarization.itertracks(yield_label=True):
                        if turn.start <= segment_mid <= turn.end:
                            segment['speaker'] = speaker
                            speaker_found = True
                            break
                    
                    # Default if no speaker found
                    if not speaker_found:
                        segment['speaker'] = 'Unknown'
                
                # Log how many speakers were found
                unique_speakers = set(s.get('speaker', 'Unknown') for s in segments)
                logger.info(f"✓ Identified {len(unique_speakers)} different speakers")
                
            except Exception as e:
                logger.error(f"Speaker identification failed: {e}")
                # Add default speaker label if diarization fails
                for segment in segments:
                    segment['speaker'] = 'Speaker'
        else:
            # No speaker diarization available - use default
            for segment in segments:
                segment['speaker'] = 'Speaker'
        # ============ END OF SPEAKER IDENTIFICATION ============
        
        return full_transcript, segments
        
    except MemoryError as e:
        logger.error(f"OUT OF MEMORY! File too large: {file_size_mb:.1f} MB")
        logger.error("Solutions:")
        logger.error("1. Set environment variable: FORCE_TINY_MODEL=true")
        logger.error("2. Process a smaller file")
        logger.error("3. Use a machine with more RAM")
        logger.error("4. Split the video into smaller parts")
        return None, None
    except Exception as e:
        logger.exception(f"Transcription failed for {file_path}: {e}")
        return None, None

def format_transcript_with_timestamps(segments):
    """Format transcript segments with timestamps"""
    formatted_lines = []
    for segment in segments:
        start_time = format_timestamp(segment['start'])
        end_time = format_timestamp(segment['end'])
        text = segment['text'].strip() if isinstance(segment['text'], str) else str(segment['text']).strip()
        formatted_lines.append(f"[{start_time} - {end_time}] {text}")
    return "\n".join(formatted_lines)

# --- LLM Summary Function ---

def summarize_video_with_llm(transcript, segments, video_filename):
    """Generate summary and timeline of key points using LLM"""
    if not transcript:
        logger.warning(f"Skipping summary for {video_filename}: empty transcript.")
        return "Summary skipped: Empty transcript provided."
    if not DEEPSEEK_API_KEY or len(DEEPSEEK_API_KEY) < 10:
        logger.error("Deepseek API key missing/invalid. Skipping summary.")
        return "Summary failed: Deepseek API key not set or invalid."

    logger.info(f"Generating summary for: {video_filename}")
    
    # Create a simplified transcript with timestamps for context
    timestamp_context = []
    for i, segment in enumerate(segments[:50]):  # Limit to first 50 segments for context
        text = segment['text'].strip() if isinstance(segment['text'], str) else str(segment['text']).strip()
        timestamp_context.append(f"[{format_timestamp(segment['start'])}] {text}")
    timestamp_text = "\n".join(timestamp_context)
    
    # Limit transcript length to avoid API limits
    max_transcript_length = 15000
    truncated = False
    if len(transcript) > max_transcript_length:
        logger.info(f"Truncating long transcript ({len(transcript)} chars) for summary...")
        transcript = transcript[:max_transcript_length]
        truncated = True
    
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        prompt_content = f"""
Analyze the following video transcript and provide a comprehensive summary with timeline:

--- FULL TRANSCRIPT{' (TRUNCATED)' if truncated else ''} ---
{transcript}
--- END TRANSCRIPT ---

--- SAMPLE TIMESTAMPS FOR REFERENCE ---
{timestamp_text}
--- END TIMESTAMPS ---

Please provide:

1. **VIDEO OVERVIEW** (2-3 sentences describing what the video is about)

2. **KEY SECTIONS AND MAIN POINTS**
List 5-8 major sections or topics covered in the video. For each section:
- Provide a clear heading
- Write 2-3 sentences explaining the main points
- Estimate the approximate time range based on content flow

3. **DETAILED KEY POINTS TIMELINE**
Identify 8-12 specific important moments, insights, or key points from the video.
For each key point:
- Provide an estimated timestamp (format as MM:SS or HH:MM:SS)
- Write a brief description (1-2 sentences) of what is discussed
- Focus on actionable insights, important facts, major announcements, or turning points

4. **KEY TAKEAWAYS**
List 3-5 main takeaways that someone should remember from this video

5. **WHO SHOULD WATCH**
Briefly describe who would benefit most from watching this video and why

Format your response clearly with headers and bullet points. Make timestamps estimates based on the content flow and structure of the transcript.
"""
        
        messages = [
            {"role": "system", "content": "You are an AI assistant that creates detailed video summaries and timelines. Provide comprehensive, well-structured summaries that help viewers understand key content without watching the entire video."},
            {"role": "user", "content": prompt_content}
        ]
        
        data = {
            "messages": messages,
            "model": "deepseek-chat",
            "max_tokens": 2048,
            "temperature": 0.3,
            "stream": False,
        }
        
        api_endpoint = "https://api.deepseek.com/v1/chat/completions"
        response = requests.post(api_endpoint, headers=headers, json=data, timeout=90)
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and result["choices"] and "message" in result["choices"][0]:
            summary_content = result["choices"][0]["message"].get("content", "").strip()
            return summary_content or "Summary failed: Empty response from API."
        return "Summary failed: Unexpected API response format."
        
    except requests.exceptions.Timeout:
        return "Summary failed: API request timed out"
    except requests.exceptions.HTTPError as http_err:
        try:
            details = response.json()
            msg = details.get('error', {}).get('message', '') if isinstance(details, dict) else ''
        except Exception:
            msg = response.text[:200]
        return f"Summary failed: API Error {response.status_code}. {msg}"
    except Exception as e:
        logger.exception(f"LLM summary error for {video_filename}: {e}")
        return f"Summary failed: Unexpected error ({type(e).__name__})"

# --- Save Functions ---

def save_transcript_to_file(transcript, segments, base_filename, transcript_folder):
    """Save full transcript with timestamps to file"""
    try:
        transcript_filename = f"{os.path.splitext(base_filename)[0]}_transcript.txt"
        transcript_filepath = os.path.join(transcript_folder, transcript_filename)
        
        # Format transcript with timestamps
        formatted_transcript = format_transcript_with_timestamps(segments)
        
        with open(transcript_filepath, 'w', encoding='utf-8') as f:
            f.write("=== FULL TRANSCRIPT WITH TIMESTAMPS ===\n\n")
            f.write(formatted_transcript)
            f.write("\n\n=== FULL TRANSCRIPT (CONTINUOUS TEXT) ===\n\n")
            f.write(transcript)
        
        logger.info(f"Transcript saved to: {transcript_filepath}")
        return True
    except Exception as e:
        logger.exception(f"Failed to save transcript for {base_filename}: {e}")
        return False

def save_summary_to_file(summary_content, base_filename, summary_folder):
    """Save summary with timeline to file"""
    try:
        summary_filename = f"{os.path.splitext(base_filename)[0]}_summary.txt"
        summary_filepath = os.path.join(summary_folder, summary_filename)
        
        with open(summary_filepath, 'w', encoding='utf-8') as f:
            f.write("=== VIDEO SUMMARY AND TIMELINE ===\n\n")
            f.write(summary_content)
        
        logger.info(f"Summary saved to: {summary_filepath}")
        return True
    except Exception as e:
        logger.exception(f"Failed to save summary for {base_filename}: {e}")
        return False

# --- Processing Functions ---

def process_video_file(file_path, url=None):
    """Process a video file: transcribe, summarize, and save results"""
    video_filename = os.path.basename(file_path)
    
    # Check file size first
    try:
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # MORE AGGRESSIVE: Compress ANY file over 20MB
        if file_size_mb > 20:
            logger.warning(f"File is {file_size_mb:.1f} MB. Converting to smaller audio file...")
            
            import subprocess
            temp_audio_path = os.path.join(AUDIO_FOLDER, f"temp_{video_filename}.mp3")
            
            # MUCH MORE AGGRESSIVE COMPRESSION
            cmd = [
                'ffmpeg', '-i', file_path,
                '-vn',  # No video
                '-acodec', 'mp3',
                '-ab', '32k',  # VERY LOW bitrate (was 64k)
                '-ar', '16000',  # 16kHz sample rate
                '-ac', '1',  # Mono audio
                '-y',  # Overwrite
                temp_audio_path
            ]
            
            try:
                logger.info("Converting with aggressive compression...")
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Check new file size
                new_size_mb = os.path.getsize(temp_audio_path) / (1024 * 1024)
                logger.info(f"Compressed from {file_size_mb:.1f} MB to {new_size_mb:.1f} MB")
                
                # If STILL too big, split it
                if new_size_mb > 30:
                    logger.warning(f"Still too large ({new_size_mb:.1f} MB). Splitting into parts...")
                    
                    # Split into 5-minute chunks
                    split_pattern = os.path.join(AUDIO_FOLDER, f"split_{video_filename}_%03d.mp3")
                    split_cmd = [
                        'ffmpeg', '-i', temp_audio_path,
                        '-f', 'segment',
                        '-segment_time', '300',  # 5 minutes per chunk
                        '-c', 'copy',
                        split_pattern
                    ]
                    
                    subprocess.run(split_cmd, capture_output=True, check=True)
                    # os.remove(temp_audio_path)  # Remove the full compressed file
                    
                    # Process each split
                    all_transcripts = []
                    all_segments = []
                    
                    for i in range(100):
                        split_file = os.path.join(AUDIO_FOLDER, f"split_{video_filename}_{i:03d}.mp3")
                        if not os.path.exists(split_file):
                            break
                        
                        logger.info(f"Processing split {i+1}...")
                        transcript, segments = transcribe_audio_with_timestamps(split_file)
                        
                        if transcript:
                            all_transcripts.append(transcript)
                            all_segments.extend(segments)
                        
                        # os.remove(split_file)  # Clean up split file
                        gc.collect()
                    
                    # Combine results
                    transcript = " ".join(all_transcripts) if all_transcripts else None
                    segments = all_segments
                    
                else:
                    # File is small enough after compression
                    transcript, segments = transcribe_audio_with_timestamps(temp_audio_path)
                    # os.remove(temp_audio_path)
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to convert: {e}")
                return "Conversion Failed"
            except FileNotFoundError:
                logger.error("ffmpeg not found!")
                return "ffmpeg Not Found"
                
        else:
            # Small file, process directly
            transcript, segments = transcribe_audio_with_timestamps(file_path)
    
    except Exception as e:
        logger.error(f"Error: {e}")
        transcript, segments = None, None
    
    # Check if we got anything
    if not transcript:
        logger.error(f"No transcript generated for {video_filename}")
        
        # Special handling for empty transcripts
        if segments is not None and len(segments) == 0:
            logger.error("File may have no audio or corrupted audio track")
            logger.info("Try: ffmpeg -i 'yourfile.mp4' -hide_banner to check for audio streams")
        
        return "Transcription Failed"
    
    # Save transcript
    if not save_transcript_to_file(transcript, segments, video_filename, TRANSCRIPTS_FOLDER):
        logger.error(f"Failed to save transcript")
        return "Save Transcript Failed"
    
    # Generate summary
    summary_result = summarize_video_with_llm(transcript, segments, video_filename)
    if "Summary failed" in summary_result:
        return "Summary Failed"
    
    # Add URL if available
    if url:
        summary_result = f"Source URL: {url}\n\n" + summary_result
    
    # Save summary
    if save_summary_to_file(summary_result, video_filename, SUMMARIES_FOLDER):
        return "Processing Success"
    return "Save Summary Failed"

def process_url_item(url):
    """Download video from URL, process it, then clean up"""
    # Download video
    video_file_path = download_audio(url, AUDIO_FOLDER)
    if not video_file_path:
        return "Download Failed"
    
    try:
        # Process the video file
        status = process_video_file(video_file_path, url)
        return status
    except Exception as e:
        logger.exception(f"Critical error processing URL {url}: {e}")
        return "Critical Error"
    # REMOVED THE finally BLOCK THAT WAS DELETING FILES
    # If you want to keep it for error handling, use this instead:
    # finally:
    #     logger.info(f"Keeping downloaded file: {video_file_path}")

def process_urls_file(url_file='urls.txt'):
    """Process all URLs from the urls.txt file"""
    urls = read_urls_from_file(url_file)
    if not urls:
        logger.info("No URLs to process.")
        return
    
    logger.info(f"Starting processing for {len(urls)} URLs from {url_file}...")
    
    # Check for yt-dlp if we have YouTube URLs
    has_youtube = any('youtube.com' in url or 'youtu.be' in url for url in urls)
    if has_youtube and not check_yt_dlp_available():
        logger.warning("YouTube URLs detected but yt-dlp not found. Install with: pip install yt-dlp")
    
    status_counts = {
        "Processing Success": 0,
        "Download Failed": 0,
        "Transcription Failed": 0,
        "Save Transcript Failed": 0,
        "Summary Failed": 0,
        "Summary Skipped": 0,
        "Save Summary Failed": 0,
        "Critical Error": 0,
    }
    
    for i, url in enumerate(urls, 1):
        logger.info(f"--- Processing URL {i}/{len(urls)} --- {url}")
        status = process_url_item(url)
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # Garbage collection between URLs
        gc.collect()
    
    # Print summary
    logger.info("=" * 70)
    logger.info("Processing Summary:")
    logger.info(f"Total URLs: {len(urls)}")
    for status, count in status_counts.items():
        if count:
            logger.info(f"- {status}: {count}")
    logger.info("=" * 70)

def process_local_folder(input_folder=INPUT_AUDIO_FOLDER):
    """Process local video files"""
    files = find_audio_files_in_folder(input_folder)
    if not files:
        logger.info(f"No audio/video files found in '{input_folder}'.")
        return
    
    logger.info(f"Found {len(files)} files in '{input_folder}'. Starting processing...")
    status_counts = {
        "Processing Success": 0,
        "Transcription Failed": 0,
        "Save Transcript Failed": 0,
        "Summary Failed": 0,
        "Summary Skipped": 0,
        "Save Summary Failed": 0,
        "Critical Error": 0,
    }
    
    for i, path in enumerate(files, 1):
        logger.info(f"--- Processing local file {i}/{len(files)} --- {path}")
        try:
            status = process_video_file(path)
        except Exception as e:
            logger.exception(f"Critical error processing {path}: {e}")
            status = "Critical Error"
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # Garbage collection between files
        gc.collect()
    
    # Print summary
    logger.info("=" * 70)
    logger.info("Local Files Processing Summary:")
    logger.info(f"Total Files: {len(files)}")
    for status, count in status_counts.items():
        if count:
            logger.info(f"- {status}: {count}")
    logger.info("=" * 70)

# --- Main ---

if __name__ == "__main__":
    logger.info("🚀 Video Transcription and Summary Tool Started")
    
    # Print system info
    try:
        import psutil
        available_memory = psutil.virtual_memory().available / (1024**3)
        total_memory = psutil.virtual_memory().total / (1024**3)
        logger.info(f"System Memory: {available_memory:.1f}GB available / {total_memory:.1f}GB total")
        
        if available_memory < 4:
            logger.warning("⚠️ Low RAM! Large files may fail. Consider:")
            logger.warning("- Using FORCE_TINY_MODEL=true")
            logger.warning("- Processing smaller files")
            logger.warning("- Closing other applications")
    except ImportError:
        logger.info("Install psutil for memory monitoring: pip install psutil")
    
    # Print model info
    if USE_FASTER_WHISPER:
        config = SPEED_CONFIGS[SPEED_MODE]
        logger.info(f"Using faster-whisper in {SPEED_MODE} mode ({config['model_size']} model)")
        logger.info(f"Settings: beam_size={config['beam_size']}, vad_filter={config['vad_filter']}")
    else:
        logger.info("Using standard whisper. Install faster-whisper for speed: pip install faster-whisper")
    
    # Check for local files first
    local_files = find_audio_files_in_folder(INPUT_AUDIO_FOLDER)
    if local_files:
        process_local_folder(INPUT_AUDIO_FOLDER)
    else:
        logger.info(f"No files found in '{INPUT_AUDIO_FOLDER}'. Processing URLs from urls.txt...")
        process_urls_file('urls.txt')
    
    logger.info("\n✅ Processing complete! Check folders:")
    logger.info("- 'transcripts/' for full transcripts with timestamps")
    logger.info("- 'summaries/' for AI-generated summaries and timelines")
