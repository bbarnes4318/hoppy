import requests
import openai
import time
import json
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
AZURE_SPEECH_KEY = '7b89559462c545e3ad4a1458d85c1b5f'
AZURE_REGION = 'eastus'
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

def transcribe_audio_with_azure(file_path):
    """Transcribes audio using Azure Speech Service."""
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY,
        'Content-Type': 'audio/wav'
    }
    params = {
        'language': 'en-US'
    }
    with open(file_path, 'rb') as audio_file:
        response = requests.post(f'https://{AZURE_REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1',
                                 headers=headers, params=params, data=audio_file)
    response_data = response.json()
    if response_data.get('RecognitionStatus') == 'Success':
        return response_data['DisplayText']
    return "Transcription failed"

def analyze_transcript_with_chatgpt(transcript):
    """
    Analyzes the call transcript using ChatGPT-4 to determine various aspects of the call.
    """
    prompt = f"""
    Analyze the following call transcript:
    {transcript}

    • A key indicator of an application being submitted: Customer gives the agent an account number and routing number OR a debit/credit card number
    • A key indicator of a quote given: A monthly premium was given to the customer
    Please answer the following questions:
    1. Was an application submitted? 
        a. If yes: Monthly premium?
    2. Was a quote given to the customer?
        a. If yes: monthly premium
    3. Did the agent tell the customer they will call back?

    Response: 
    1. Yes
    a. $70
    2. Yes
    a. $70
    3. No
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
        transcript = transcribe_audio_with_azure(temp_file_name)
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
