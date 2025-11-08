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

### Objectives

Using the provided call transcript, you are tasked with accomplishing the following:

1. **Extract Customer Information:**
   - **First Name:** Identify and confirm the customer’s first name as mentioned during the conversation.
   - **Last Name:** Identify and confirm the customer’s last name as mentioned during the conversation.
   - **Phone Number:** Extract the customer’s phone number from the conversation.

2. **Determine Story Consistency:**
   - **Inconsistencies:** Analyze the transcribed conversation between the motor vehicle accident litigation prospect and the qualifying representative to identify any inconsistencies or changes in the prospect’s account of the accident.
   - **Key Details:** Focus on the following elements to determine consistency:
     - **Time:** When did the accident occur?
     - **Location:** Where did the accident happen?
     - **Circumstances:** How did the accident occur?
     - **Involvement:** Who was involved in the accident?
     - **Consequences:** What injuries or damages were mentioned?

3. **Detect Potential Cheating by Qualifiers:**
   - **Call Back Indicators:** Determine if the legal office’s qualifier suggests calling the prospect back, especially if it happens close to the threshold where the call becomes billable.
   - **Timing of Suggestion:** Pay special attention to the timing of when the qualifier suggests a callback. If it occurs near the billable call duration threshold, highlight this as a potential attempt to avoid billing.
   - **Pattern Analysis:** Look for patterns across multiple calls where the same strategy is used to potentially cheat the system.

### Steps for Analysis

1. **Identify Key Details:**
   - Extract the key details as initially described by the prospect, focusing on the time, location, circumstances, parties involved, and any injuries or damages reported.

2. **Track Changes:**
   - Monitor how these key details are described throughout different parts of the conversation. Note any changes, omissions, or discrepancies in the prospect’s story as the conversation progresses.

3. **Contextual Analysis:**
   - Evaluate whether any changes in the prospect’s story might be attributed to natural clarification or if they indicate significant inconsistencies. Assess the context in which these changes occur to determine their impact on the overall narrative.

4. **Detect Call Back Indicators:**
   - Identify any points in the conversation where the qualifier suggests a callback. Compare the timing of these suggestions to the known billable call duration threshold.

5. **Summarize Findings:**
   - Provide a comprehensive summary of whether the prospect’s story remained consistent or if significant inconsistencies were detected. Clearly indicate the specific parts of the conversation where inconsistencies were found.
   - Report any instances where the qualifier suggested a callback, particularly if it occurred near the billable duration threshold. Highlight these as potential attempts to avoid billing.

6. **Confidence Level:**
   - Assign a confidence level (e.g., high, medium, low) to your analysis, reflecting how confident you are in the consistency or inconsistency of the prospect's story and in detecting any potential cheating attempts.

### Examples for Reference

- **Consistent Story Example:**
  - **Introduction:** "I was driving on Main Street at around 5:00 PM. I had just passed the intersection with 7th Avenue when a car from the opposite direction suddenly swerved into my lane and hit my car head-on. I was going about 30 mph, and the other driver didn’t seem to be paying attention."
  - **Middle:** "Yes, I remember clearly that it was 5:00 PM because I had just left work. I was on Main Street, heading home. The accident happened just after I crossed 7th Avenue. The other driver came out of nowhere, crossing into my lane. I was maintaining my speed at 30 mph."
  - **End:** "As I mentioned earlier, it was 5:00 PM on Main Street, just past 7th Avenue. I was going 30 mph when the other car suddenly crossed into my lane and we collided head-on. The other driver was clearly not paying attention, possibly distracted."
  - **Consistency:** The time, location, speed, and circumstances remain consistent throughout the conversation.

- **Inconsistent Story Example:**
  - **Introduction:** "I was driving on Main Street around 5:00 PM. I was stopped at a red light when a car rear-ended me. The impact pushed me into the intersection, and my car was badly damaged."
  - **Middle:** "Actually, it might have been closer to 4:30 PM, and I wasn’t completely stopped. I was slowing down as I approached the intersection when the car behind me didn’t stop in time and hit me. The collision pushed me forward, but I managed to stop before entering the intersection."
  - **End:** "Now that I think about it, it was probably around 4:45 PM. I was definitely moving slowly, maybe around 10 mph, when the other car hit me from behind. It wasn’t a full stop, but the impact was still strong enough to push me into the middle of the intersection, and my car was damaged on both the front and rear."
  - **Inconsistency:** The prospect’s story changes regarding the time of the accident, whether they were stopped or moving, and the extent of the impact, suggesting potential unreliability in their account.
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
