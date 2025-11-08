import requests
import os

# AssemblyAI API key
api_key = 'c34fcd7703954d55b39dba9ec1a7b04c'

def download_file(url, file_path):
    response = requests.get(url)
    with open(file_path, 'wb') as file:
        file.write(response.content)

def transcribe(file_path):
    def upload_file(file_path):
        headers = {'authorization': api_key}
        with open(file_path, 'rb') as f:
            response = requests.post('https://api.assemblyai.com/v2/upload', headers=headers, files={'file': f})
        return response.json()['upload_url']

    def get_transcription(upload_url):
        json = {"audio_url": upload_url}
        headers = {"authorization": api_key, "content-type": "application/json"}
        response = requests.post('https://api.assemblyai.com/v2/transcript', json=json, headers=headers)
        return response.json()['id']

    def check_status(transcript_id):
        endpoint = f'https://api.assemblyai.com/v2/transcript/{transcript_id}'
        headers = {"authorization": api_key}
        while True:
            response = requests.get(endpoint, headers=headers)
            status = response.json()['status']
            if status == 'completed':
                return response.json()['text']
            elif status == 'failed':
                return 'Transcription failed'

    upload_url = upload_file(file_path)
    transcript_id = get_transcription(upload_url)
    return check_status(transcript_id)

def read_urls_from_file(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]

urls = read_urls_from_file('urls.txt')  # File containing URLs

for index, url in enumerate(urls):
    file_name = f"downloaded_audio_{index}.mp3"
    download_file(url, file_name)

    # Transcribe the downloaded file
    print(f"Transcribing file {file_name}...")
    transcription = transcribe(file_name)
    print(f"Transcription for file {file_name}:")
    print(transcription)


