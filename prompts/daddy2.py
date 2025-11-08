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
        "10kormore": "Did the prospect have $10,000 or more in credit card and/or personal debt?",
        "TotalDebt": "What is total amount of their credit card and/or personal loan debt?",
        "Understanding": "Did the prospect understand that the call was regarding credit card and/or personal loan debt",
        "AlreadyEnrolled": "Did the prospect say that they are ALREADY enrolled in another debt settlement program?",
        "Bankruptcy": "Did the prospect say that they are in the middle of an active bankruptcy?",
        "conversiontosale": "Did the prospect say yes to our debt settlement program offer?",
        "followUP": "If a sale was NOT made, was a follow-up time set?"
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