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

Analyze the provided call transcript to determine the following information:

**Your Objectives:**

    **1. Billable Call Determination:**
    Assess whether the call is billable based solely on the following criteria. Do not consider sales outcomes when determining billability.

    **Criteria for a Non-Billable Call:**
    A call is **Not Billable** only if it meets **one or more** of these conditions:

    **1. Unqualified Customer:**
    - The customer is **65 years or older** (born before December 26, 1959).
    - The customer has **Medicare, Medicaid, Tricare, or employer-provided health coverage**.
    - The customer earns **less than $15,000 per year**.

    **2. Vulgar or Prank Call:**
    - The customer is **clearly wasting the agent’s time** with irrelevant or disruptive behavior.
    - The customer uses **vulgar language** during the call.

    **3. Do Not Call (DNC) Request:**
    - The customer explicitly states they want to be placed on the **Do Not Call list**.
    - The customer calls solely to **complain about receiving too many calls**.

    **4. Already Renewed 2025 Health Plan:**
    - The customer explicitly states they have already **renewed their 2025 ACA Health Plan**.

    **Output for Billability:**
    - **Billable:** [Yes/No]
    - **Reason (if Not Billable):** [State the specific criterion from the list above.]

    **2. Sale or Enrollment Determination:**
    Analyze the transcript to identify if a sale occurred, following the definitions below. Separate this analysis from billability determination.

    **Ways an Agent Makes a Sale:**

    **1. AOR (Agent of Record) Change Sale:**
    - Occurs when a customer requests changes to their existing ACA Health Insurance Plan.
    - A valid AOR change requires:
      - Verification via third-party confirmation (e.g., adding a third party to the call or using an OTP sent via email or text).
      - The customer only needs to remain on the call long enough for their name to be confirmed by the third party.

    **2. New Enrollment Sale:**
    - Occurs when a customer does not have an existing plan, and the agent submits a new application.
    - A valid new enrollment requires:
      - Portions of the customer’s SSN (last 4, first 5, or full 9 digits).
      - Confirmation of application submission with specific details such as:
        - Acknowledgment that the application was submitted.
        - Policy effective dates or reference numbers.

    **3. Renewal for 2025 as a New Application:**
    - Treat renewals for 2025 as new enrollments (not AOR changes).
    - A valid renewal sale requires:
      - Verification similar to new enrollment sales, including portions of the customer’s SSN or equivalent.

    **Output for Sale Determination:**
    - **Sale:** [Yes/No]
    - **Type:** [New Enrollment, Renewal, or AOR Change].
    - **Reason (if No Sale):** [Explain why no sale occurred, referencing the definitions above.]

    **3. Supporting Information:**
    - **Prior Enrollments:** [Mention of enrollments or renewals with dates].
    - **Household Members:** [Number of members].
    - **Customer Name:** [Full Name].
    - **Phone Number:** [Number].
    - **Agent Name:** [First Name].

    **4. Abrupt Ending:**
    - Did the call end abruptly? [Yes/No]
    - **Reason:** [Explanation].
    - **Last Thing Said:** [Content].
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