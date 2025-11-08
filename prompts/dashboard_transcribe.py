import requests
import openai
import time
import os
import csv
from fastapi import FastAPI, Request

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
app = FastAPI()

ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

CSV_FILE_PATH = r"C:\Users\Jimbo\crm-dashboard\results.csv"

def download_audio(recording_url, file_name):
    """Downloads the recording from VAPI.ai."""
    response = requests.get(recording_url)
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
    """Submits an audio file for transcription on AssemblyAI."""
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
    """Analyzes the call transcript using OpenAI to determine key call outcomes."""
    prompt = f"""
    Analyze the following call transcript:
    {transcript}

    # AI Task: Determining Call Outcomes from Transcripts

## Task Description:
You are tasked with analyzing call transcripts between our AI Voice Agent and ACA Health Insurance customers. Your goal is to determine specific outcomes of each call by identifying key information, and output the results as Boolean values (TRUE or FALSE) for each of the seven predefined categories, including date and time where applicable. **Note**: There cannot be both an appointment and a callback. An appointment must include a specific date and time, while a callback does not.

## Instructions:
1. **Read the provided call transcript carefully.**
2. **For each of the seven categories, determine whether the condition is met (TRUE or FALSE).**
3. **If an appointment was made, extract the specific date and time.**
4. **Ensure that both 'appointment' and 'callback' cannot be TRUE at the same time.**
5. **Provide a brief justification for each determination, citing relevant parts of the transcript.**
6. **Present your findings in the specified output format.**

## Categories:
- contacted: Did the customer answer and engage in the call?
- renewal: Did the customer agree to receive renewal documents?
- consent: Did the customer give consent to act as agent of record?
- appointment: Did the customer agree to a specific appointment?
- callback: Did the customer request a callback?
- addons: Did the customer express interest in life or dental insurance?
- remove: Did the customer ask to stop calling?
    """
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "Analyze the transcript for insurance outcomes."},
                  {"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']

def update_dashboard(customer_phone, analysis_result):
    """Sends the analysis results back to the CRM server."""
    dashboard_url = "https://yourserver.com/update-dashboard"
    payload = {
        "phone": customer_phone,
        "analysis_result": analysis_result
    }

    headers = {
        "Authorization": f"Bearer {your_auth_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(dashboard_url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"Successfully updated dashboard for {customer_phone}")
    except requests.exceptions.RequestException as e:
        print(f"Error updating dashboard for {customer_phone}: {e}")

@app.post("/analyze")
async def analyze_recording(request: Request):
    """Handles the incoming recording URL and processes the recording."""
    data = await request.json()
    customer_phone = data.get('customer_phone')
    recording_url = data.get('recording_url')
    
    # Download, transcribe, and analyze the recording
    temp_file_name = 'temp_audio.mp3'
    try:
        download_audio(recording_url, temp_file_name)
        assemblyai_url = upload_audio_to_assemblyai(temp_file_name)
        transcript = transcribe_audio(assemblyai_url)
        analysis_result = analyze_transcript_with_chatgpt(transcript)
        update_dashboard(customer_phone, analysis_result)
    finally:
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)

    return {"status": "success", "message": "Recording analyzed and sent to dashboard."}
