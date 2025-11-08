import requests
from pydub import AudioSegment
from io import BytesIO

def read_urls_from_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()

        # Split URLs using a blank line as the delimiter
        urls = content.split('\n\n')

        # Clean up and reconstruct URLs
        cleaned_urls = []
        for url in urls:
            cleaned_url = ''.join(url.split())  # Remove all whitespace within a URL
            cleaned_urls.append(cleaned_url)

        return cleaned_urls

def download_and_convert(url, index):
    response = requests.get(url)
    audio = AudioSegment.from_file(BytesIO(response.content))
    audio.export(f"output_{index}.mp3", format="mp3")

urls = read_urls_from_file('urls.txt')  # File containing URLs

for i, url in enumerate(urls):
    download_and_convert(url, i)
    print(f"Downloaded and converted: output_{i}.mp3")