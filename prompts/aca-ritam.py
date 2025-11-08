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

    # Debugging: Print response status and content
    print("Upload Response Status Code:", response.status_code)
    print("Upload Response Content:", response.text)

    if response.status_code == 200:
        try:
            return response.json().get('upload_url')
        except requests.exceptions.JSONDecodeError:
            print("Error decoding JSON response.")
            return None
    else:
        print("Failed to upload the audio. Check the API key or endpoint.")
        return None

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

ACA Health Insurance Transcription Analysis

Enhance the analysis of ACA Health Insurance application calls by identifying sales scenarios and determining call billability, incorporating a new sales method, and clarifying non-billable call criteria.

*Ways an Agent Makes a Sale:*  

**First Way: AOR (Agent of Record) Change Sale:**  
- If the customer needs changes to their existing ACA Health Insurance Plan, an Agent of Record (AOR) change is required.
- Valid AOR change requires:
  - Verification either through third-party confirmation by adding a third part on to the phone call or OTP code through email or text message. 
  - Customer only has to be on the call long enough for their name to be confirmed by the third party.

**Second Way: New Enrollment Sale:**  
- If the customer does not have an existing plan, the application proceeds as a new enrollment. 
- Valid sale conditions include providing Portions of the customer's SSN (last 4, first 5, or full 9 digits) and confirming the application submission with specific details such as acknowledgement that an application was submitted, policy effective dates or reference numbers.

**Third Way: Renewal for 2025 as a New Application:**  
- Treat renewing for 2025 as a new enrollment, with no need for AOR change.
- Valid renewal sale requires portions of SSN or similar verification as in new enrollment sales.

**Non-Billable Call Conditions:**
- Customer not knowing why they are on the phone call.
- Already covered through Medicare, Medicaid, Tricare, VA, or employer coverage.
- Eligible for Medicaid thus making customer ineligible for an ACA health plan.
- Born before December 12, 1959.

# Steps

1. **Transcript Analysis:** Review call transcript for mention of existing or new application.
2. **Sale Identification:** Determine if a sale occurred through any of the three defined ways.
3. **Billability Assessment:** Check transcript against non-billable conditions to assess whether the call is billable.

# Output Format

Provide a structured analysis in the following detailed format:

1. **Prior Enrollments:**
   - Mentions of 2025 enrollment, total enrollments, dates.

2. **Sale Determination:**
   - If a sale occurred, identify the method ('New Enrollment,' 'AOR Change,' or 'Renewal'). If no sale, note the reasons and any follow-up by the agent.

3. **Household Members:** 
   - Number of members on the health insurance plan.

4. **Customer Information:**
   - Full Name and Phone number.

5. **Agent Information:**
   - Agent First Name.

6. **Billable Call Determination:**
   - Is the call billable based on conditions, and why?

7. **Abrupt Ending:**
   - Indication and context of abrupt call ending.

# Examples

**Example Start**

- **Call Transcript:** [Insert Representative Call Transcript Here]

- **Output:**

  1. **Prior Enrollments:**
     - Yes, enrolled for 2025 once.
     - Dates: January 15, 2024.
  
  2. **Sale Determination:**
     - Sale: Yes 
      -Type: Renewal
  
  3. **Household Members:**
     - Two members listed.

  4. **Customer Information:**
     - Full Name: John Doe.
     - Phone: 123-456-7890.

  5. **Agent Information:**
     - First Name: Alice.

  6. **Billable Call Determination:**
     - Not billable due to customer having Medicare coverage.
  
  7. **Abrupt Ending:**
     - Discussion on SSN verification.

**Example End**

# Notes

- Any calls involving detailed discussions about plans other than ACA or over age limits are non-billable.
- Make sure that any renewals are treated with the same procedures as new enrollments for 2025.
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