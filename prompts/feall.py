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
    {transcript}

### Objectives:

Based on the call transcript, you are tasked with determining the following:

1. Is the call a billable call? 
**Billable Call Determination:** Assess if the call qualifies as a 'billable call'—a call for which the buyer is charged.  
   - A call is considered **Billable** unless any of the following conditions apply:
     - a. The customer resides in a nursing home.
     - b. The customer has been diagnosed with COPD.
     - c. The customer explicitly states they do NOT have an active payment method (e.g., bank account, debit card, or credit card).
     - d. The customer requires a power of attorney for financial decisions.
     - e. The customer is unaware that the call is about final expense or life insurance.
     - f. The customer is on the call solely to waste the agent's time or as a prank.

2. Was an application submitted?
**Final Expense Application Determination:** Identify if an application for final expense insurance was submitted during the call.  
   - An application is considered submitted if the customer provides **any** of the following:
     - a. Checking account number and routing number.
     - b. Savings account number and routing number.
     - c. Debit card number.
     - d. Credit card number.

3. **If an application was submitted, provide:**
     - a. Monthly premium.
     - b. Insurance Carrier.
     - c. Coverage Amount.
     - d. Policy Type (choose one):
       - 1. **Level:** For customers in good health with 'first-day coverage'.
       - 2. **Graded/Modified:** For customers with health issues; involves a waiting period before the death benefit applies.
       - 3. **Guaranteed Issue:** For customers who cannot qualify for Level or Modified/Graded plans due to health.
     - e. Was the policy declined? 
       - 1. If so, did the insured apply for a modifed/graded or guaranteed issue product after being declined?

4. **Quote Provided Determination:** If an application was **not** submitted, provide the details of the quote offered by the agent:
   - a. Monthly Premium.
   - b. Insurance Carrier.
   - c. Coverage Amount.
   - d. Policy Type (Level, Modified/Graded, Guaranteed Issue).
   - e. Reason for not purchasing the policy.
   - f. Was a follow-up set? (Yes or No) If Yes, specify the day and time.'

4. **Abrupt Ending to the Phone Call Determination** We are having issues with calls abruptly ending right around the time the prospect moves into the application for a policy. The application for a policy begins when health questions start. 
   - a. Did the call end abruptly?
        If So:
               - 1. Were medical questions already answered? 
 	       - 2. Did the customer already agree to a coverage amount and monthly premium? 
  	       - 3. Did the customer already choose a beneficiary?
               - 4. Did the customer already give a social security number? 
               - 5. Did the customer already provide their bank account routing and account numbers OR a credit card number?
	       - 6. What was the last question asked before the call ended abruptly?

5. **Is this a fraudulent call? 

Signs of Fraudulent Calls:
• The customer’s answers to various questions point to a pattern of very similar answers when the answer response should be a wide pool of answers. (i.e. Most people say they are ‘self-employed’ and make exactly ‘$22,000’ per year.)
• The customers are very agreeable throughout the call.
• The customers drop off the line in the middle of a call resulting in an abrupt ending to the call.
• Customers announce that they can’t hear or are having trouble hearing before eventually disconnecting from the call
    """
    response = openai.ChatCompletion.create(
        model="gpt-4o",
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
