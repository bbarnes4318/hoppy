import requests
import openai
import time
import json
import os
from datetime import datetime
from flask import Flask, render_template, jsonify

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
app = Flask(__name__)

ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
RINGBA_API_KEY = '09f0c9f071a1efe5c7417f4c8f9ec34ef7cf5b59eb7b85dfbb4bca13414585a761cf1bcfe7ddc6e34b9c663f86a231c9cf746162577f415e1c6bd6be60d60874dfc5568b9434131f746064fcf1517c0c8df332dfe3a74654e4caeb7d0203d353fe351327172f544f20616ce504fe14f9e55f4fc7'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

call_data = []

def fetch_ringba_calls():
    headers = {'Authorization': f'Bearer {RINGBA_API_KEY}'}
    response = requests.get('https://api.ringba.com/v2/calls', headers=headers)
    return response.json()

def process_call_data(call):
    callerid = call['callerid']
    timestamp = call['timestamp']
    agent = call['agent']
    duration = call['duration']
    cost = call['cost']
    return {
        'callerid': callerid,
        'timestamp': timestamp,
        'agent': agent,
        'duration': duration,
        'cost': cost,
        'application': '',
        'premium': '',
        'carrier': '',
        'coverage': ''
    }

### 2. Real-time processing of call data and recordings

def download_mp3(url, file_name):
    response = requests.get(url)
    with open(file_name, 'wb') as file:
        file.write(response.content)

def upload_audio_to_assemblyai(file_path):
    headers = {'authorization': ASSEMBLYAI_API_KEY}
    response = requests.post('https://api.assemblyai.com/v2/upload',
                             headers=headers,
                             files={'file': open(file_path, 'rb')})
    return response.json()['upload_url']

def transcribe_audio(assemblyai_url):
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

def process_call(url, call):
    temp_file_name = 'temp_audio.mp3'
    try:
        download_mp3(url, temp_file_name)
        assemblyai_url = upload_audio_to_assemblyai(temp_file_name)
        transcript = transcribe_audio(assemblyai_url)
        analysis_result = analyze_transcript_with_chatgpt(transcript)
        
        # Parse analysis result and update call data
        call['application'] = analysis_result.get('application', '')
        call['premium'] = analysis_result.get('premium', '')
        call['carrier'] = analysis_result.get('carrier', '')
        call['coverage'] = analysis_result.get('coverage', '')

        call_data.append(call)
    finally:
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)

### 3. Dashboard for data visualization

@app.route('/')
def index():
    return render_template('index.html', calls=call_data)

@app.route('/refresh')
def refresh_data():
    calls = fetch_ringba_calls()
    for call in calls:
        call_info = process_call_data(call)
        process_call(call['recording_url'], call_info)
    return jsonify(call_data)

if __name__ == "__main__":
    app.run(debug=True)
