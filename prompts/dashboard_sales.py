import requests
import openai
import time
import json
import os
import csv
import sys
import pandas as pd
import logging
import re

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# Replace with your actual API keys
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

# CSV file path
CSV_FILE_PATH = r"C:\Users\Jimbo\Documents\pete\customers.csv"

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        status = check_response.json()['status']
        if status == 'completed':
            return check_response.json()['text']
        elif status == 'error':
            return "Transcription failed"
        else:
            time.sleep(5)

def analyze_transcript_with_chatgpt(transcript):
    """
    Analyzes the call transcript using ChatGPT-4 to determine various aspects of the call.
    """
    prompt = f"""
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

---

**Call Transcript:**
{transcript}

---

**Output Format:**

- contacted: TRUE/FALSE (Justification)
- renewal: TRUE/FALSE (Justification)
- consent: TRUE/FALSE (Justification)
- appointment: TRUE/FALSE (If TRUE, include date and time. Justification)
- callback: TRUE/FALSE (Justification)
- addons: TRUE/FALSE (Justification)
- remove: TRUE/FALSE (Justification)
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an assistant that analyzes call transcripts for specific outcomes."},
            {"role": "user", "content": prompt}
        ]
    )

    if response and 'choices' in response and response['choices']:
        analysis_result = response['choices'][0]['message']['content']
        return analysis_result.strip()
    else:
        return "Analysis failed due to an error."

def update_customer_csv(first_name, phone_number, analysis_result):
    """Updates the customer CSV file based on the analysis result."""
    df = pd.read_csv(CSV_FILE_PATH, dtype=str)
    mask = (df['first_name'] == first_name) & (df['phone'] == phone_number)

    # Parse the analysis result
    updates = {}
    lines = analysis_result.split('\n')
    for line in lines:
        if ':' in line:
            key, rest = line.split(':', 1)
            key = key.strip().lower()
            if key in ['contacted', 'renewal', 'consent', 'appointment', 'callback', 'addons', 'remove']:
                value = rest.strip()
                if 'TRUE' in value.upper():
                    updates[key] = 'TRUE'
                else:
                    updates[key] = 'FALSE'
                # Handle appointment date and time
                if key == 'appointment' and 'TRUE' in value.upper():
                    date_time_match = re.search(r'\((.*?)\)', value)
                    if date_time_match:
                        date_time_info = date_time_match.group(1)
                        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_time_info)
                        time_match = re.search(r'(\d{1,2}:\d{2}\s*(AM|PM)?)', date_time_info, re.IGNORECASE)
                        if date_match:
                            updates['appointment_date'] = date_match.group(1)
                        if time_match:
                            updates['appointment_time'] = time_match.group(1)

    for key, value in updates.items():
        df.loc[mask, key] = value

    df.to_csv(CSV_FILE_PATH, index=False)
    logging.info(f"Updated {first_name} ({phone_number}) in customers.csv with analysis results.")

def process_call(url, first_name, phone_number):
    """Orchestrates the process of handling a call."""
    temp_file_name = 'temp_audio.mp3'
    try:
        download_mp3(url, temp_file_name)
        assemblyai_url = upload_audio_to_assemblyai(temp_file_name)
        transcript = transcribe_audio(assemblyai_url)
        analysis_result = analyze_transcript_with_chatgpt(transcript)
        update_customer_csv(first_name, phone_number, analysis_result)
    finally:
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)
    return analysis_result

def process_all_calls():
    """Processes all calls from the 'customers.csv' file."""
    df = pd.read_csv(CSV_FILE_PATH, dtype=str)
    for _, row in df.iterrows():
        url = row.get('recording_url', '')
        first_name = row['first_name']
        phone_number = row['phone']
        if url:
            print(f"Processing recording for {first_name} ({phone_number})")
            result = process_call(url, first_name, phone_number)
            print("Analysis Result:\n", result)
            print("---------------------------------------------------")
        else:
            logging.warning(f"No recording URL for {first_name} ({phone_number})")

if __name__ == "__main__":
    process_all_calls()
