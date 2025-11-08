import os
import requests
import openai
import time
import json

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# AssemblyAI and OpenAI API keys
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

# Function to read URLs from a file
def read_urls_from_file(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.read().split('\n\n') if line.strip()]

# Function to download MP3 from URL
def download_mp3(url, file_name):
    response = requests.get(url)
    with open(file_name, 'wb') as file:
        file.write(response.content)
    return file_name

# Function to transcribe audio using AssemblyAI
def transcribe_audio(file_path):
    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/json"
    }
    response = requests.post('https://api.assemblyai.com/v2/upload',
                             headers=headers,
                             data=open(file_path, 'rb'))
    audio_url = response.json()['upload_url']
    
    transcription_request = {"audio_url": audio_url}
    response = requests.post("https://api.assemblyai.com/v2/transcript",
                             json=transcription_request,
                             headers=headers)
    transcript_id = response.json()['id']

    while True:
        response = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
        status = response.json()['status']
        if status == 'completed':
            return response.json()['text']
        elif status == 'failed':
            return None
        time.sleep(5)

def analyze_transcript(transcript):
    # Prepare the prompt with the transcript and structured questions
    questions = {
        "Understanding Insurance Type": "Did the prospect understand that the call was regarding final expense or life insurance?",
        "Willingness to Speak": "Did the prospect want to speak with the agent about final expense or life insurance?",
        "Age Check": "Did the prospect say that they are 81 years old or greater?",
        "Power of Attorney": "Did the prospect say that they needed a power of attorney present with them to make financial decisions?",
        "Living Situation": "Did the prospect say that they live in a nursing home or assisted living facility?",
        "Third-Party Confirmation": "Did someone else come onto the call and imply that the prospect lives in a nursing home or assisted living facility?",
        "Financial Means": "Did the prospect say that they do NOT have an active bank account or credit card?",
        "Medical Condition": "Did the prospect say that they have been diagnosed or treated for alzheimer's or dementia?",
        "Call Duration": "Did the agent tell the prospect that they will call them back and then ended the call with the prospect before the duration of the call duration reached 180 seconds?",
        "Pricing Discussion": "Did the agent give the prospect a price on their final expense policy and then ended the call before the call duration reached 180 seconds?",
        "Policy Sale Indicators": "Were there key indicators of a policy being sold, such as the prospect giving a routing number and account number or a debit or credit card number to the agent?",
        "Policy Sale Confirmation": "Was a policy sold and if so, what is the carrier name, monthly premium, and the date of the first payment?",
        "Follow-Up Arrangement": "If a sale was NOT made, was a follow-up time set?"
    }
    
    responses = {}
    for key, question in questions.items():
        # Format the prompt as a conversation
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Text: {transcript}\nQuestion: {question}\nAnswer:"}
        ]

        # Send the conversation to the OpenAI Chat model
        response = openai.ChatCompletion.create(model="gpt-4-turbo-preview", messages=messages, max_tokens=60)

        # Extract and store the response
        assistant_message = response.choices[0].message['content']
        responses[key] = assistant_message.strip()

    return responses

# Main workflow
def main():
    urls = read_urls_from_file('urls.txt')  # File containing URLs

    for index, url in enumerate(urls):
        # Download MP3 file
        mp3_file_name = f"audio_{index}.mp3"
        download_mp3(url, mp3_file_name)
        
        # Transcribe audio file
        transcription = transcribe_audio(mp3_file_name)
        
        # Analyze transcription
        if transcription:
            analysis = analyze_transcript(transcription)
            print(f"Analysis for {mp3_file_name}: {analysis}")
        else:
            print(f"Failed to transcribe {mp3_file_name}")

if __name__ == "__main__":
    main()