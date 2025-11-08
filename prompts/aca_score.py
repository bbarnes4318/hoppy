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
    try:
        # Make the request with a timeout
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        
        # Check if we actually got audio content
        content_type = response.headers.get('content-type', '')
        if not any(audio_type in content_type.lower() for audio_type in ['audio', 'mp3', 'mpeg']):
            print(f"Warning: Unexpected content type: {content_type}")
        
        # Write the content to file
        with open(file_name, 'wb') as file:
            file.write(response.content)
            
        # Verify the file was created and has content
        if os.path.getsize(file_name) == 0:
            raise Exception("Downloaded file is empty")
            
        print(f"Successfully downloaded {len(response.content)} bytes to {file_name}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {str(e)}")
        raise
    except Exception as e:
        print(f"Error saving file: {str(e)}")
        raise

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

**ACA Health Insurance Application and Agent of Record Changes**

*There are 2 possible ways in which an agent makes a sale:*

*First Way:* **Agent of Record (AOR) change Sale**:

1. If the customer has an existing ACA Health Insurance Plan then the application must be processed by completing an Agent of Record (AOR) change. There are two ways to complete an AOR change: 

- By adding a 3rd party onto the phone call and obtaining their approval to process the AOR change
- By using a text or email verification process and getting the code from the customer that was texted to them

Note: If 1 of 2 things mentioned above do not occur, then there was no AOR change processed. 


*Second Way:* **New Enrollment Sale**

2. If the customer DOES NOT have an existing ACA Health Insurance Plan then the application will be processed as a 'new enrollment'. 

A sale is valid if the **customer provides their 9-digit Social Security number OR the first 5-digits OR the last 4-digts** and **any one or more** of the following occurs:

- The customer **explicitly states** they have submitted a health insurance application.
- The customer provides or receives a **code or reference number** associated with the application submission or confirmation.
- A **policy effective date** or **start date for coverage** is discussed.
---

**ACA Health Insurance Application and Agent of Record Changes Analysis**

Analyze the call transcript to determine whether a **sale** occurred and provide answers to the questions below:

## Question & Response Format

Based on the conditions listed above, please provide the following answers:

1. Did a licensed agent answer the live transfer phone call? Yes or No

2. Was a sale made? 
	a. If 'Yes', was it a 'New Enrollment' or 'AOR Change'?
	b. If 'No', why did the customer not move forward with a plan or AOR change? (Provide the customer's reason for not enrolling or changing their AOR)
		i. If No sale was made, Did the agent state that they will call or text the customer back?

3. Customer Information
	a. **Customer Full Name**: Extract from the transcript.
	b. **Customer Phone**: Extract from the transcript.

4. Agent Information
	b. **Agent First Name**: Extract from the transcript.

5. Quick Call Summary
    """
    response = openai.ChatCompletion.create(
        model="gpt-4o-2024-11-20",
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