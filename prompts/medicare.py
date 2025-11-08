import requests
import openai
import time
import json
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

def read_urls_from_file(file_name='urls.txt'):
    """Reads URLs from a file and returns a list of URLs."""
    with open(file_name, 'r') as file:
        urls = file.readlines()
    return [url.strip() for url in urls if url.strip()]

def download_mp3(url, file_name):
    """Downloads an MP3 file from a given URL."""
    response = requests.get(url)
    with open(file_name, 'wb') as file:
        file.write(response.content)

def upload_audio_to_assemblyai(file_path):
    """Uploads an audio file to AssemblyAI and returns the upload URL."""
    headers = {'authorization': ASSEMBLYAI_API_KEY}
    response = requests.post('https://api.assemblyai.com/v2/upload',
                             headers=headers,
                             files={'file': open(file_path, 'rb')})
    return response.json()['upload_url']

def transcribe_audio(assemblyai_url):
    """Submits an audio file for transcription on AssemblyAI and waits for the transcription to complete."""
    headers = {'authorization': ASSEMBLYAI_API_KEY, 'content-type': 'application/json'}
    json_data = {'audio_url': assemblyai_url}
    response = requests.post('https://api.assemblyai.com/v2/transcript', json=json_data, headers=headers)
    transcript_id = response.json()['id']

    while True:
        check_response = requests.get(f'https://api.assemblyai.com/v2/transcript/{transcript_id}', headers=headers)
        if check_response.json()['status'] == 'completed':
            return check_response.json()['text']
        elif check_response.json()['status'] == 'failed':
            return "Transcription failed"

def analyze_transcript_with_chatgpt(transcript):
    """
    Analyzes the call transcript using ChatGPT-4 to determine various aspects of the call.
    """
    prompt = f"""
    Analyze the following call transcript:
    {transcript}

    Based on the transcript, determine:
    1. Is the customer submits an application for Medicare Insurance (Yes or No)
           """
    response = openai.ChatCompletion.create(
        model="gpt-4-0125-preview",
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
    temp_file_name = 'temp_audio.mp3'
    try:
        download_mp3(url, temp_file_name)
        assemblyai_url = upload_audio_to_assemblyai(temp_file_name)
        transcript = transcribe_audio(assemblyai_url)
        analysis_result = analyze_transcript_with_chatgpt(transcript)
    finally:
        # Clean up by removing the temporary audio file
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)
    
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
