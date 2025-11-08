import requests
import openai
import json
import os
import re

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
AZURE_SPEECH_KEY = '7b89559462c545e3ad4a1458d85c1b5f'
AZURE_REGION = 'eastus'
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

def transcribe_audio_with_azure(file_path):
    """Transcribes audio using Azure Speech Service."""
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY,
        'Content-Type': 'audio/wav'
    }
    params = {
        'language': 'en-US'
    }
    with open(file_path, 'rb') as audio_file:
        response = requests.post(f'https://{AZURE_REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1',
                                 headers=headers, params=params, data=audio_file)
    response_data = response.json()
    if response_data.get('RecognitionStatus') == 'Success':
        return response_data['DisplayText']
    return "Transcription failed"

def extract_credit_card_info(transcript):
    """Extracts credit card information from the transcript using OpenAI GPT-4."""
    prompt = f"""
    Extract all credit card numbers mentioned in the following call transcript:
    {transcript}

    Format each credit card number found in a separate line.
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4-0125-preview",
        messages=[
            {"role": "system", "content": "You are an AI trained to extract credit card information from call transcripts."},
            {"role": "user", "content": prompt}
        ]
    )
    
    if response and 'choices' in response and response['choices']:
        extracted_info = response['choices'][0]['message']['content']
        print(f"Extracted Information: {extracted_info}")
        return extracted_info.strip().split('\n')
    else:
        return []

def luhn_check(card_number):
    """Validates credit card number using the Luhn algorithm."""
    card_number = re.sub(r'\D', '', card_number)  # Remove non-digit characters
    digits = [int(digit) for digit in card_number]
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    total = sum(digits)
    return total % 10 == 0

def analyze_credit_cards(credit_cards):
    """Analyzes extracted credit card numbers and returns their validity."""
    results = []
    for card in credit_cards:
        print(f"Checking card number: {card}")
        if re.fullmatch(r'\d{13,19}', card):  # Ensure the card number has between 13 and 19 digits
            is_valid = luhn_check(card)
            results.append("Valid" if is_valid else "Invalid")
        else:
            results.append("Invalid")
    return results

def process_call(url):
    """Orchestrates the process of handling a call: downloading, uploading for transcription, transcribing, and analyzing."""
    temp_file_name = 'temp_audio.mp3'
    try:
        download_mp3(url, temp_file_name)
        transcript = transcribe_audio_with_azure(temp_file_name)
        print(f"Transcript: {transcript}")
        if transcript != "Transcription failed":
            credit_cards = extract_credit_card_info(transcript)
            print(f"Extracted Credit Cards: {credit_cards}")
            if credit_cards:
                analysis_result = analyze_credit_cards(credit_cards)
                return analysis_result
            else:
                return ["No credit card numbers detected"]
        else:
            return ["Inconclusive"]
    finally:
        # Clean up by removing the temporary audio file
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)

def process_all_calls():
    """Processes all calls from the URLs provided in the 'urls.txt' file."""
    urls = read_urls_from_file()
    for url in urls:
        print(f"Processing: {url}")
        result = process_call(url)
        print(f"Analysis Result: {result}")
        print("---------------------------------------------------")

if __name__ == "__main__":
    process_all_calls()
