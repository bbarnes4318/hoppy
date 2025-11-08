import os
import requests
import whisper
import csv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Paths
CSV_FILE_PATH = r'C:\Users\Jimbo\Documents\FE Python Transcription App\aca_sales.csv'
AUDIO_FOLDER = "audio_files"  # Folder to store downloaded audio

# Whisper model initialization
model = whisper.load_model("base")  # Options: tiny, base, small, medium, large

# Initialize counters for new ACA applications and AOR changes
new_aca_applications_count = 0
aor_changes_count = 0


def read_urls_from_file(file_name='urls.txt'):
    """Reads URLs from a file and returns a list of URLs."""
    if not os.path.exists(file_name):
        logging.error(f"File not found: {file_name}")
        return []
    with open(file_name, 'r') as file:
        urls = file.readlines()
    return [url.strip() for url in urls if url.strip()]


def download_audio(url, output_folder):
    """Downloads an MP3 file from the given URL and saves it in the specified folder."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    audio_file_name = os.path.join(output_folder, os.path.basename(url.split('?')[0]) + ".mp3")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(audio_file_name, 'wb') as f:
            f.write(response.content)
        logging.info(f"Downloaded audio to {audio_file_name}")
    except requests.RequestException as e:
        logging.error(f"Failed to download audio: {e}")
        return None
    return audio_file_name


def transcribe_audio(file_path):
    """Transcribes audio using the local Whisper model."""
    logging.info(f"Transcribing audio: {file_path}")
    try:
        result = model.transcribe(file_path)
        return result.get("text", "")
    except Exception as e:
        logging.error(f"Transcription failed for {file_path}: {e}")
        return ""


def analyze_transcript_with_prompt(transcript):
    """
    Analyzes the call transcript based on a detailed prompt.
    """
    prompt = f"""
    Analyze the following call transcript:
    {transcript}

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
    logging.info(f"Analyzing transcript:\n{prompt}")
    return prompt  # Placeholder for actual LLM integration.


def process_call(url, output_folder):
    """Processes a single call: download, transcribe, analyze, and save results."""
    audio_file_name = download_audio(url, output_folder)
    if not audio_file_name:
        logging.error(f"Failed to download audio for URL: {url}")
        return None

    try:
        # Transcribe audio
        transcript = transcribe_audio(audio_file_name)
        if transcript:
            analysis_result = analyze_transcript_with_prompt(transcript)
            logging.info(f"Analysis Result for {audio_file_name}:\n{analysis_result}")
        else:
            logging.error("No transcript generated.")
        return analysis_result
    finally:
        # Clean up downloaded audio
        if os.path.exists(audio_file_name):
            os.remove(audio_file_name)


def process_all_calls():
    """Processes all calls from the URLs provided in the 'urls.txt' file."""
    urls = read_urls_from_file()
    if not urls:
        logging.error("No URLs to process.")
        return

    os.makedirs(AUDIO_FOLDER, exist_ok=True)

    for url in urls:
        logging.info(f"Processing: {url}")
        transcript = process_call(url, AUDIO_FOLDER)
        if transcript:
            logging.info(f"Transcript Analysis:\n{transcript}")
        else:
            logging.error(f"Failed to process {url}")
        logging.info("---------------------------------------------------")

if __name__ == "__main__":
    process_all_calls()
