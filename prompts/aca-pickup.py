import requests
import openai
import time
import os
import csv

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

# CSV file path
CSV_FILE_PATH = r'C:\Users\Jimbo\Documents\FE Python Transcription App\aca_sales.csv'

# Initialize counters for new ACA applications and AOR changes
new_aca_applications_count = 0
aor_changes_count = 0

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

ACA Health Insurance Call Qualification Analysis
Analyze ACA Health Insurance calls to determine if a licensed agent joined the call, whether the call progressed to a potential sale, and identify the reasons for the call not progressing further.

Qualification Goals:
Agent Presence: Identify if a licensed agent joined the call.
Call Outcome: Determine why the call did not progress further if a sale was not made.

Steps

Transcript Analysis:

Review the transcript for indicators of:
A licensed agent joining the call.
The reason the call did not result in a sale.

Agent Identification:
Confirm whether a licensed agent was present during the call or if nobody answered.

Outcome Assessment:
If the call was answered, determine why the call did not lead to a sale (e.g., customer declined, eligibility issues, call ended early, etc.).

Output Format

Provide a structured analysis in the following format:

Agent Presence:
Did a licensed agent join the call? (Yes/No)
If no, note: “No agent joined the call.”

Call Outcome:
Was the call answered? (Yes/No)
If answered, provide the reason the call did not progress further (e.g., customer declined, ineligible for ACA, call ended abruptly, etc.).

Customer Information:
Full Name
Phone Number

Agent Information:
Agent First Name (if applicable)

Abrupt Ending:
Note if the call ended abruptly and provide context.

Example

Example Start

Call Transcript: [Insert Representative Call Transcript Here]

Output:

Agent Presence:
Yes, a licensed agent joined the call.

Call Outcome:
The call was answered, but the customer declined to proceed due to cost concerns.

Customer Information:
Full Name: John Doe
Phone: 123-456-7890

Agent Information:
First Name: Alice

Abrupt Ending:
No abrupt ending noted.

Example End

Notes:
Ensure clarity on why the call did not progress to a sale.
Calls where no agent joined or the customer did not answer should be noted explicitly.
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
    global new_aca_applications_count, aor_changes_count
    temp_file_name = 'temp_audio.mp3'
    try:
        download_mp3(url, temp_file_name)
        assemblyai_url = upload_audio_to_assemblyai(temp_file_name)
        transcript = transcribe_audio(assemblyai_url)
        analysis_result = analyze_transcript_with_chatgpt(transcript)
        
        # Safely extract values from analysis lines
        analysis_lines = analysis_result.split("\n")

        # Initialize default values
        customer_name = "N/A"
        agent_name = "N/A"
        new_app = "N/A"
        aor_change = "N/A"
        fraud = "N/A"

        # Safely extract values by checking both length and content of each line
        for line in analysis_lines:
            if "Customer Full Name" in line:
                customer_name = line.split(": ")[1] if ": " in line else "N/A"
            elif "Agent First Name" in line:
                agent_name = line.split(": ")[1] if ": " in line else "N/A"
            elif "ACA Health Insurance Application" in line:
                new_app = line.split(": ")[1] if ": " in line else "N/A"
            elif "AOR change or plan change" in line:
                aor_change = line.split(": ")[1] if ": " in line else "N/A"
            elif "fraudulent" in line:
                fraud = line.split(": ")[1] if ": " in line else "N/A"

        # Append the data to the CSV
        add_to_csv(customer_name, agent_name, new_app, aor_change, fraud)
        
        # Count the new ACA applications and AOR changes
        if new_app == 'Yes':
            new_aca_applications_count += 1
        if aor_change == 'Yes':
            aor_changes_count += 1

    finally:
        # Clean up by removing the temporary audio file
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)
    
    return analysis_result

def add_to_csv(customer_name, agent_name, new_app, aor_change, fraud):
    """Appends the analysis results to the CSV file."""
    # Open the CSV in append mode ('a')
    with open(CSV_FILE_PATH, mode='a', newline='') as file:  # Open in append mode
        writer = csv.writer(file)
        # Append the new row with the analysis results
        writer.writerow([customer_name, agent_name, new_app, aor_change, fraud])

def process_all_calls():
    """Processes all calls from the URLs provided in the 'urls.txt' file."""
    urls = read_urls_from_file()
    for url in urls:
        print(f"Processing: {url}")
        result = process_call(url)
        print("Analysis Result:\n", result)
        print("---------------------------------------------------")

    # Print the final report
    print(f"Total New ACA Health Applications: {new_aca_applications_count}")
    print(f"Total Agent of Record (AOR) and/or Plan Changes: {aor_changes_count}")

if __name__ == "__main__":
    process_all_calls()