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

# Call Analysis: ACA Health Insurance Application Submission

## Indicators of Existing ACA Marketplace Policy:
- The customer agrees to update their Agent of Record (AOR) to the agent on the call.
- The agent or customer mentions an existing Marketplace application or policy.
- The agent confirms the customer’s existing plan by locating them in the Marketplace system.

## Indicators of AOR Update and Plan Change:
- A third-party (e.g., enrollment specialist or verification representative) joins the call to assist with the application process.
- The call concludes successfully with the third-party's involvement, without abrupt disconnection.

## Indicators of New ACA Health Insurance Application Submission:
- The customer explicitly states they have submitted a health insurance application.
- The customer provides or receives a code or reference number associated with application submission or confirmation.
- A policy effective date or start date for coverage is discussed.
- No third-party assistance is involved in the call.

## Indicators of Non-Submission of ACA Health Insurance Application:
- The customer abruptly disconnects the call before completing the application process.
- The customer shows reluctance or refuses to proceed with the application.
- Key steps, such as code sharing or third-party involvement, are not completed during the call.

## Indicators of Potential Fraudulent Activity:
- The customer is overly agreeable throughout the call.
- The call ends abruptly after the customer drops off the line.
- The customer complains of hearing issues before disconnecting.
- The customer mentions being incentivized to participate in the call.
- The customer indicates they were instructed to act or speak in a specific way.
- Inconsistent answers are provided by the customer during the call.
- The customer states they are self-employed.

## Question & Response Format:

1. **Does the customer have an existing ACA Marketplace plan?**

   - **If No:**
     - **Did the customer submit a new application for coverage?**
     - **If Yes:** Which insurance carrier?
     - **Customer's First Name and Last Name?**

   - **If Yes:**
     - **Was a third-party (e.g., Marketplace representative) involved in the call to assist with a new application or Agent of Record (AOR) change?**
     - **If Yes:** Which insurance carrier?
     - **Customer's First Name and Last Name?**

2. **Is there any indication that this might be a fraudulent call?**

3. **Provide a brief summary of the call and its outcome.**
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
