import requests
import openai
import time
import json
import os
import pandas as pd

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

EXCEL_FILE_PATH = r'C:\Users\Jimbo\Desktop\feall\stats.xlsx'  # Correctly using a raw string for the file path

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

def split_transcript(transcript, max_length=8000):
    """Splits the transcript into chunks that do not exceed the specified token limit."""
    words = transcript.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(' '.join(current_chunk)) > max_length:
            chunks.append(' '.join(current_chunk[:-1]))
            current_chunk = [word]

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

def analyze_transcript_with_chatgpt(transcript):
    """
    Analyzes the call transcript using ChatGPT-4 to determine various aspects of the call.
    """
    transcript_chunks = split_transcript(transcript)
    combined_analysis = ""

    for chunk in transcript_chunks:
        prompt = (
            f"{chunk}\n\n"
            "### Objectives:\n\n"
            "Task: Extract relevant data from the given phone call recording and populate the specified fields in the corresponding Excel file.\n\n"
            "Instructions:\n\n"
            "Recording URL: Extract the URL of the recording and place it in the 'Recording' field.\n\n"
            "Customer Details:\n\n"
            "Full Name: Extract the customer's first and last name and place it in the 'Customer Full Name' field.\n"
            "Phone Number: Extract the customer's phone number and place it in the 'Customer Phone' field.\n\n"
            "Call Classification:\n\n"
            "Billable: Determine if the call is billable and select 'Yes' or 'No' in the 'Billable' field.\n"
            "Reason Not Billable: If the call is not billable, provide the reason in the 'Reason Not Billable' field.\n"
            "Abrupt Ending: Identify if the customer dropped off the call suddenly and select 'Yes' or 'No' in the 'Abrupt Ending' field.\n\n"
            "Agent Interaction:\n\n"
            "Last Question: Record the last question asked by the agent before the customer dropped from the call, if applicable.\n"
            "Application Submitted: Indicate if an application was submitted by selecting 'Yes' or 'No' in the 'Application' field.\n\n"
            "Policy Details:\n\n"
            "Premium: Extract the monthly premium for the final expense policy and place it in the 'Premium' field.\n"
            "Carrier: Identify the insurance company applied for and place it in the 'Carrier' field.\n"
            "Coverage: Extract the amount of coverage applied for and place it in the 'Coverage' field.\n\n"
            "Quoted Information:\n\n"
            "Quote Premium: Extract the quoted monthly premium and place it in the 'Quote Premium' field.\n"
            "Quote Carrier: Identify the carrier quoted and place it in the 'Quote Carrier' field.\n"
            "Quote Coverage: Extract the quoted coverage amount and place it in the 'Quote Coverage' field.\n\n"
            "Customer Decision:\n\n"
            "Reason Not Buy: If the customer did not apply for a policy, provide the reason in the 'Reason Not Buy' field.\n"
            "Agent Improvement: Suggest what the agent could have done better to increase the chances of making the sale, and place it in the 'Agent' field.\n\n"
            "Follow-Up:\n\n"
            "Follow-Up Planned: Indicate if a follow-up is planned by selecting 'Yes' or 'No' in the 'Follow-Up' field.\n\n"
            "File Path: Excel file (.xlsx) located at C:\\Users\\Jimbo\\Desktop\\feall\\stats.xlsx.\n\n"
            "Note: Each new phone call should be recorded on a separate row in the Excel file with the corresponding fields completed based on the above instructions.\n\n"
            "Example Call:\n"
            "\"The following represents a new phone call: \"https://media.ringba.com/recording-public?v=v1&k=\""
        )
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a highly intelligent AI trained to analyze call transcripts for insurance purposes."},
                {"role": "user", "content": prompt}
            ]
        )
        
        if response and 'choices' in response and response['choices']:
            analysis_result = response['choices'][0]['message']['content']
            combined_analysis += analysis_result.strip() + "\n"
        else:
            combined_analysis += "Analysis failed for a chunk due to an error.\n"

    return combined_analysis.strip()

def update_excel_with_analysis(analysis, url):
    """Updates the Excel file with the analysis result."""
    # Load the existing Excel file
    df = pd.read_excel(EXCEL_FILE_PATH)
    
    # Create a new row with the extracted data
    new_row = pd.DataFrame([{
        "Recording": url,
        "Customer Full Name": extract_field(analysis, "Customer Full Name"),
        "Customer Phone": extract_field(analysis, "Customer Phone"),
        "Billable": extract_field(analysis, "Billable"),
        "Reason Not Billable": extract_field(analysis, "Reason Not Billable"),
        "Abrupt Ending": extract_field(analysis, "Abrupt Ending"),
        "Last Question": extract_field(analysis, "Last Question"),
        "Application": extract_field(analysis, "Application Submitted"),
        "Premium": extract_field(analysis, "Premium"),
        "Carrier": extract_field(analysis, "Carrier"),
        "Coverage": extract_field(analysis, "Coverage"),
        "Quote Premium": extract_field(analysis, "Quote Premium"),
        "Quote Carrier": extract_field(analysis, "Quote Carrier"),
        "Quote Coverage": extract_field(analysis, "Quote Coverage"),
        "Reason Not Buy": extract_field(analysis, "Reason Not Buy"),
        "Agent": extract_field(analysis, "Agent Improvement"),
        "Follow-Up": extract_field(analysis, "Follow-Up Planned")
    }])
    
    # Concatenate the new row to the DataFrame
    df = pd.concat([df, new_row], ignore_index=True)
    
    # Save the updated DataFrame back to the Excel file
    df.to_excel(EXCEL_FILE_PATH, index=False)

def extract_field(analysis, field_name):
    """Extracts a specific field from the analysis result."""
    # You may need to adjust this function to properly extract each specific field
    try:
        start = analysis.index(f"{field_name}:") + len(f"{field_name}:")
        end = analysis.index("\n", start)
        return analysis[start:end].strip()
    except ValueError:
        return ""

def process_call(url):
    """Orchestrates the process of handling a call: downloading, uploading for transcription, transcribing, analyzing, and updating the Excel file."""
    temp_file_name = 'temp_audio.mp3'
    try:
        download_mp3(url, temp_file_name)
        assemblyai_url = upload_audio_to_assemblyai(temp_file_name)
        transcript = transcribe_audio(assemblyai_url)
        analysis_result = analyze_transcript_with_chatgpt(transcript)
        update_excel_with_analysis(analysis_result, url)
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
