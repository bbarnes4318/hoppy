import requests
import openai
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

def upload_audio_to_assemblyai(file_path):
    """Uploads an audio file to AssemblyAI and returns the upload URL."""
    headers = {'authorization': ASSEMBLYAI_API_KEY}
    with open(file_path, 'rb') as file:
        response = requests.post('https://api.assemblyai.com/v2/upload',
                                 headers=headers,
                                 files={'file': file})
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
    
    Based on the transcript, determine:
    1. A brief call summary including key details and outcomes.
    2. Identify the following data points of the prospect:
       - Full name
       - Email
       - Phone
       - Name of Company
    3. Is the prospect interested in speaking to someone about AI?
    4. Does the prospect want to be contacted via a phone call?
    5. Does the prospect want to be contacted via an email?
    6. Grade the prospect’s interest level on a grading scale of 1 to 10, with 10 being the most interested and 1 being the least interested.
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4-0125-preview",
        messages=[
            {"role": "system", "content": "You are a highly intelligent AI trained to analyze call transcripts."},
            {"role": "user", "content": prompt}
        ]
    )
    
    if response and 'choices' in response and response['choices']:
        analysis_result = response['choices'][0]['message']['content']
        return analysis_result.strip()
    else:
        return "Analysis failed due to an error."

def process_audio_files(file_paths):
    """Processes multiple audio files for transcription and analysis."""
    results = []
    for file_path in file_paths:
        try:
            print(f"Processing file: {file_path}")
            assemblyai_url = upload_audio_to_assemblyai(file_path)
            transcript = transcribe_audio(assemblyai_url)
            analysis_result = analyze_transcript_with_chatgpt(transcript)
            results.append((file_path, analysis_result))
        except Exception as e:
            results.append((file_path, f"An error occurred: {str(e)}"))
    return results

if __name__ == "__main__":
    # List of paths to your MP3 files, updated with the provided file names
    file_paths = [
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-155824_4078265136-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-160326_8188646174-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-162137_6603950111-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-162847_2602440032-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-163409_2602440032-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-163614_7605988700-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164001_2252754325-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164037_8434076803-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164143_7706851777-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164229_2065122469-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164346_5633321561-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164513_2192132530-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164630_8146969605-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164743_2187281148-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-164832_9178307565-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165014_2075836747-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165021_7202833797-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165110_6195503651-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165141_2126853050-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165242_7322059677-all (1).mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165333_7814851001-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165350_2027839116-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165406_7142771708-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165440_6052244173-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-165634_7275963258-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-170157_5096282600-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-170539_8655583595-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-170605_2485431000-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-170754_8592826545-all.mp3',
        'C:\\Users\\Jimbo\\Desktop\\recording\\20240308-171243_3305266984-all.mp3',
    ]
    analysis_results = process_audio_files(file_paths)
    
    for file_path, result in analysis_results:
        print(f"File: {file_path}\nAnalysis Result:\n{result}\n{'-'*50}")

