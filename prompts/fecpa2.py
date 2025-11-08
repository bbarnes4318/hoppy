import openai
import requests
import os
from azure.cognitiveservices.speech import SpeechConfig, SpeechRecognizer, AudioConfig, ResultReason
from pydub import AudioSegment
import time

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# Set ffmpeg and ffprobe paths
current_dir = os.path.dirname(os.path.abspath(__file__))
ffmpeg_path = os.path.join(current_dir, "ffmpeg", "bin", "ffmpeg.exe")
ffprobe_path = os.path.join(current_dir, "ffmpeg", "bin", "ffprobe.exe")

AudioSegment.ffmpeg = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

# Verify the correct version of the openai package is being used
expected_version = "0.28.0"
assert openai.__version__ == expected_version, f"Expected openai version {expected_version}, but got {openai.__version__}"

AZURE_SPEECH_KEY = '9cf9e1f9409c45c9a26d9b347205ae50'
AZURE_REGION = 'eastus'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

def read_urls_from_file(file_name='urls.txt'):
    """Reads URLs from a file and returns a list of URLs."""
    print(f"Reading URLs from {file_name}")
    if not os.path.exists(file_name):
        raise FileNotFoundError(f"{file_name} does not exist.")
    
    with open(file_name, 'r') as file:
        urls = file.readlines()
    
    urls = [url.strip() for url in urls if url.strip()]
    print(f"Found URLs: {urls}")
    return urls

def download_mp3(url, file_name):
    """Downloads an MP3 file from a given URL."""
    print(f"Downloading audio from: {url}")
    response = requests.get(url)
    if response.status_code == 200:
        with open(file_name, 'wb') as file:
            file.write(response.content)
        print(f"Downloaded audio file from {url} to {file_name}")
    else:
        print(f"Failed to download audio file from {url}, status code: {response.status_code}")

def convert_mp3_to_wav(mp3_file, wav_file):
    """Converts an MP3 file to WAV format."""
    print(f"Converting {mp3_file} to {wav_file}")
    audio = AudioSegment.from_mp3(mp3_file)
    audio.export(wav_file, format="wav")
    print(f"Converted {mp3_file} to {wav_file}")

def check_audio_file(file_path):
    """Checks if the audio file is valid and playable."""
    try:
        audio = AudioSegment.from_file(file_path)
        duration = len(audio)
        if duration == 0:
            raise ValueError("Audio file is empty")
        print(f"Audio file '{file_path}' is valid with duration {duration}ms")
        return True
    except Exception as e:
        print(f"Invalid audio file '{file_path}': {str(e)}")
        return False

def transcribe_audio_with_azure(file_path):
    """Transcribes an audio file using Azure Speech Services."""
    try:
        speech_config = SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_REGION)
        audio_config = AudioConfig(filename=file_path)
        recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        result = recognizer.recognize_once()

        if result.reason == ResultReason.RecognizedSpeech:
            return result.text
        elif result.reason == ResultReason.NoMatch:
            return "No speech could be recognized"
        else:
            return f"Recognition failed: {result.reason}"
    except Exception as e:
        return f"Exception during recognition: {str(e)}"

def analyze_transcript_with_chatgpt(transcript):
    """
    Analyzes the call transcript using ChatGPT-4 to determine various aspects of the call.
    """
    prompt = f"""
    Analyze the following call transcript:
    {transcript}

    The objective is to determine if an application for final expense insurance was submitted during a phone call with a customer. The primary indicator of an application being submitted is the provision of payment information by the customer. If the customer provides their bank routing and account numbers, and/or their credit or debit card number, it is a clear indication that an application was submitted.

    ### Main Question:
    **Was a final expense insurance application submitted?**

    ### If an application was submitted, please provide the following details:

    1. **Monthly Premium**: The amount the customer will pay each month.
    2. **Carrier**: The insurance company providing the policy.
    3. **Coverage Amount**: The total benefit amount of the policy.
    4. **Date of Initial Payment**: The date when the first payment is scheduled or was made.
    5. **Policy Type**: Indicate whether the policy is:
       - Level Policy
       - Graded/Modified Policy
       - Guaranteed Issue Policy
    6. **Customer Full Name**: The full name of the customer as provided during the application process.
    7. **Payment Information Provided**: Specify if the customer provided:
       - Bank routing and account numbers
       - Credit or debit card number
    """
    response = openai.ChatCompletion.create(
        model="gpt-4-0315",
        messages=[
            {"role": "system", "content": "You are a highly intelligent AI trained to analyze call transcripts for insurance purposes."},
            {"role": "user", "content": prompt}
        ]
    )
    
    if response and 'choices' in response and response['choices']:
        analysis_result = response['choices'][0]['message']['content']
        return analysis_result.strip()
    else:
        return "Analysis failed due to an error."

def process_call(url):
    """Orchestrates the process of handling a call: downloading, uploading for transcription, transcribing, and analyzing."""
    temp_mp3_file = 'temp_audio.mp3'
    temp_wav_file = 'temp_audio.wav'
    analysis_result = None
    try:
        print(f"Current directory: {os.getcwd()}")
        print(f"Downloading audio from: {url}")
        download_mp3(url, temp_mp3_file)
        
        # Check if the file exists immediately after downloading
        if not os.path.exists(temp_mp3_file):
            raise ValueError(f"File {temp_mp3_file} does not exist after downloading")
        
        print(f"Downloaded audio file to {temp_mp3_file}")
        
        file_size = os.path.getsize(temp_mp3_file)
        print(f"File size: {file_size} bytes")
        
        print("Downloaded audio, now validating...")
        if not check_audio_file(temp_mp3_file):
            raise ValueError("Downloaded audio file is invalid")

        print(f"Converting {temp_mp3_file} to WAV format for Azure Speech recognition...")
        convert_mp3_to_wav(temp_mp3_file, temp_wav_file)

        print("Valid audio, now transcribing with Azure...")
        transcript = transcribe_audio_with_azure(temp_wav_file)
        print(f"Transcription result: {transcript}")
        print("Analyzing transcription with ChatGPT...")
        analysis_result = analyze_transcript_with_chatgpt(transcript)
        print(f"Analysis result: {analysis_result}")
    except Exception as e:
        print(f"Error processing call: {str(e)}")
    finally:
        # Clean up by removing the temporary audio files
        if os.path.exists(temp_mp3_file):
            os.remove(temp_mp3_file)
        if os.path.exists(temp_wav_file):
            os.remove(temp_wav_file)
    
    return analysis_result

def process_all_calls():
    """Processes all calls from the URLs provided in the 'urls.txt' file."""
    urls = read_urls_from_file()
    for url in urls:
        print(f"Processing: {url}")
        result = process_call(url)
        print("Analysis Result:\n", result)
        print("---------------------------------------------------")

if __name__ == "__main__":
    process_all_calls()
