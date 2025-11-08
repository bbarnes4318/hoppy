import requests
import openai
import time
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

def download_wav(url, file_name):
    """Downloads a WAV file from a given URL."""
    print(f"Downloading WAV file from URL: {url}")
    response = requests.get(url)
    with open(file_name, 'wb') as file:
        file.write(response.content)
    print(f"Downloaded WAV file to: {file_name}")

def upload_audio_to_assemblyai(file_path):
    """Uploads an audio file to AssemblyAI and returns the upload URL."""
    print(f"Uploading audio file to AssemblyAI: {file_path}")
    headers = {'authorization': ASSEMBLYAI_API_KEY}
    response = requests.post('https://api.assemblyai.com/v2/upload',
                             headers=headers,
                             files={'file': open(file_path, 'rb')})
    if response.status_code != 200:
        print(f"Error uploading file: {response.json()}")
        return None
    upload_url = response.json()['upload_url']
    print(f"Uploaded audio file. Upload URL: {upload_url}")
    return upload_url

def transcribe_audio(assemblyai_url):
    """Submits an audio file for transcription on AssemblyAI and waits for the transcription to complete."""
    print(f"Submitting audio for transcription: {assemblyai_url}")
    headers = {'authorization': ASSEMBLYAI_API_KEY, 'content-type': 'application/json'}
    json_data = {'audio_url': assemblyai_url}
    response = requests.post('https://api.assemblyai.com/v2/transcript', json=json_data, headers=headers)
    if response.status_code != 200:
        print(f"Error submitting for transcription: {response.json()}")
        return None
    transcript_id = response.json()['id']
    print(f"Submitted for transcription. Transcript ID: {transcript_id}")

    while True:
        print(f"Checking transcription status for ID: {transcript_id}")
        check_response = requests.get(f'https://api.assemblyai.com/v2/transcript/{transcript_id}', headers=headers)
        if check_response.status_code != 200:
            print(f"Error checking transcription status: {check_response.json()}")
            return None
        status = check_response.json()['status']
        print(f"Transcription status: {status}")
        if status == 'completed':
            print("Transcription completed")
            return check_response.json()['text']
        elif status == 'failed':
            print("Transcription failed")
            print("Error details:", check_response.json())
            return "Transcription failed"
        time.sleep(5)

def analyze_transcript_with_chatgpt(transcript):
    """
    Analyzes the call transcript using ChatGPT-4 to determine various aspects of the call.
    """
    prompt = f"""
    Analyze the following call transcript:
    {transcript}

Call Analysis: ACA Health Insurance Policy Renewal

Summary of the Call:

Human Conversation
Did our voice bot speak to an answering machine or a real human?
a. Answering machine
b. Real human

Current Plan Satisfaction:
Does the customer intend to renew their current health insurance plan?
a. Yes
b. No

2025 New Bundle Packages:
Which bundle package did the customer express interest in?
a. Dental
b. Vision
c. Life Insurance
d. a and b
e. a and c
f. b and c
g. All of the above
h. None

Provide any additional relevant notes:
    """
    print("Analyzing transcript with ChatGPT")
    response = openai.ChatCompletion.create(
        model="gpt-4-0125-preview",
        messages=[
            {"role": "system", "content": "You are a highly intelligent AI trained to analyze call transcripts for insurance purposes."},
            {"role": "user", "content": prompt}
        ]
    )
    
    if response and 'choices' in response and response['choices']:
        analysis_result = response['choices'][0]['message']['content']
        print("Analysis completed")
        return analysis_result.strip()
    else:
        print("Analysis failed due to an error")
        return "Analysis failed due to an error."

def process_call(url):
    """Orchestrates the process of handling a call: downloading, uploading for transcription, transcribing, and analyzing."""
    temp_file_name = 'temp_audio.wav'
    try:
        download_wav(url, temp_file_name)
        assemblyai_url = upload_audio_to_assemblyai(temp_file_name)
        if not assemblyai_url:
            return "Upload failed, skipping transcription."
        transcript = transcribe_audio(assemblyai_url)
        if transcript != "Transcription failed":
            analysis_result = analyze_transcript_with_chatgpt(transcript)
        else:
            analysis_result = "Transcription failed, analysis skipped."
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
