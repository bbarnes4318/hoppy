# Import libraries
import os
import whisper
import logging
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Paths
AUDIO_FOLDER = "audio_files"  # Folder to store downloaded audio
os.makedirs(AUDIO_FOLDER, exist_ok=True)  # Create the folder if it doesn't exist

# Whisper model initialization
model = whisper.load_model("base")  # Use "base" or "small" for better accuracy

# Deepseek API key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Function to read URLs from file
def read_urls_from_file(file_name='urls3.txt'):
    """Reads URLs from a file and returns a list of URLs."""
    if not os.path.exists(file_name):
        logging.error(f"File not found: {file_name}")
        return []
    with open(file_name, 'r') as file:
        urls = file.readlines()
    return [url.strip() for url in urls if url.strip()]

# Function to download audio
def download_audio(url, output_folder):
    """Downloads an MP3 file from the given URL and saves it in the specified folder."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    audio_file_name = os.path.join(output_folder, os.path.basename(url.split('?')[0]) + ".mp3")

    try:
        response = requests.get(url, timeout=10)  # 10-second timeout
        response.raise_for_status()
        with open(audio_file_name, 'wb') as f:
            f.write(response.content)
        logging.info(f"Downloaded audio to {audio_file_name}")
    except requests.RequestException as e:
        logging.error(f"Failed to download audio: {e}")
        return None
    return audio_file_name

# Function to transcribe audio
def transcribe_audio(file_path):
    """Transcribes audio using Whisper."""
    logging.info(f"Transcribing audio: {file_path}")
    try:
        result = model.transcribe(file_path)
        return result.get("text", "")
    except Exception as e:
        logging.error(f"Transcription failed for {file_path}: {e}")
        return ""

def analyze_transcript_with_llm(transcript):
    """
    Sends the transcript to Deepseek's API for analysis.
    """
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Define messages array with system and user messages
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant specialized in analyzing call transcripts."
            },
            {
                "role": "user",
                "content": f"""
                Analyze the following call transcript:
                {transcript}

                Your Objectives:

                1. Billable Call Determination:
                Assess whether the call is billable based solely on the following criteria. Do not consider sales outcomes when determining billability.

                Criteria for a Non-Billable Call:
                - The call is **Not Billable** if it meets one or more of these conditions:
                  1. **Unqualified Customer**:
                     - The customer is 65 years or older (born on or before December 26, 1959).
                     - The customer has Medicare, Medicaid, Tricare, or employer-provided health coverage.
                     - The customer earns less than $15,000 per year.
                  2. **Vulgar or Prank Call**:
                     - The customer is clearly wasting the agent's time with irrelevant or disruptive behavior.
                     - The customer uses vulgar language during the call.
                  3. **Do Not Call (DNC) Request**:
                     - The customer explicitly states they want to be placed on the Do Not Call list.
                     - The customer calls solely to complain about receiving too many calls.
                  4. **Already Renewed 2025 Health Plan**:
                     - The customer explicitly states they have already renewed their 2025 ACA Health Plan.

                Output for Billability:
                - Billable: [Yes/No]
                - Reason (if Not Billable): [State the specific criterion from the list above.]

                2. Sale or Enrollment Determination:
                Analyze the transcript to identify if a sale occurred, following the definitions below. Separate this analysis from billability determination.

                Ways an Agent Makes a Sale:
                1. **AOR (Agent of Record) Change Sale**:
                   - Occurs when a customer requests changes to their existing ACA Health Insurance Plan.
                   - A valid AOR change requires:
                     - Verification via third-party confirmation (e.g., adding a third party to the call or using an OTP sent via email or text).
                     - The customer only needs to remain on the call long enough for their name to be confirmed by the third party.
                2. **New Enrollment Sale**:
                   - Occurs when a customer does not have an existing plan, and the agent submits a new application.
                   - A valid new enrollment requires:
                     - Portions of the customer's SSN (last 4, first 5, or full 9 digits).
                     - Confirmation of application submission with specific details such as:
                       - Acknowledgment that the application was submitted.
                       - Policy effective dates or reference numbers.
                3. **Renewal for 2025 as a New Application**:
                   - Treat renewals for 2025 as new enrollments (not AOR changes).
                   - A valid renewal sale requires:
                     - Verification similar to new enrollment sales, including portions of the customer's SSN or equivalent.

                Output for Sale Determination:
                - Sale: [Yes/No]
                - Type: [New Enrollment, Renewal, AOR Change, or No Sale]
                - Reason (if No Sale): [Explain why no sale occurred, referencing the definitions above.]

                3. Supporting Information:
                - Prior Enrollments: [Mention of enrollments or renewals with dates, if any]
                - Household Members: [Number of members, if mentioned]
                - Customer Name: [Full Name, if provided]
                - Phone Number: [Number, if provided]
                - Agent Name: [First Name, if provided]

                4. Abrupt Ending:
                - Did the call end abruptly? [Yes/No]
                - Reason: [Explanation, if applicable]
                - Last Thing Said: [Content of the last statement made during the call]
                """
            }
        ]
        
        # Prepare the request payload
        data = {
            "messages": messages,
            "model": "deepseek-chat",
            "max_tokens": 2048,
            "temperature": 0.2,
            "stream": False,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "response_format": {
                "type": "text"
            },
            "stop": None,
            "tools": None,
            "tool_choice": "none",
            "logprobs": False,
            "top_logprobs": None
        }

        # Make the API request
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        # Handle the response
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                logging.error("No choices in response")
                return "Analysis failed: No response content"
        else:
            logging.error(f"API request failed with status {response.status_code}")
            logging.error(f"Response: {response.text}")
            return f"Analysis failed: API request failed with status {response.status_code}"
            
    except requests.exceptions.Timeout:
        logging.error("Deepseek API request timed out")
        return "Analysis failed: API request timed out"
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {str(e)}")
        return f"Analysis failed: {str(e)}"
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return f"Analysis failed: {str(e)}"

# Function to process all calls
def process_all_calls():
    """Processes all calls from the URLs in the 'urls3.txt' file."""
    urls = read_urls_from_file()
    if not urls:
        logging.error("No URLs to process.")
        return

    for url in urls:
        logging.info(f"Processing: {url}")
        audio_file_name = download_audio(url, AUDIO_FOLDER)
        if not audio_file_name:
            logging.error(f"Failed to download audio for URL: {url}")
            continue

        try:
            # Transcribe audio
            logging.info("Starting transcription...")
            transcript = transcribe_audio(audio_file_name)
            if transcript:
                logging.info("Transcription completed. Starting analysis...")
                analysis_result = analyze_transcript_with_llm(transcript)
                logging.info(f"Analysis Result for {audio_file_name}:\n{analysis_result}")
            else:
                logging.error("No transcript generated.")
        except Exception as e:
            logging.error(f"Processing failed: {e}")
        finally:
            # Clean up downloaded audio
            if os.path.exists(audio_file_name):
                os.remove(audio_file_name)
            logging.info(f"Finished processing for URL: {url}")
        logging.info("---------------------------------------------------")

# Run the script
if __name__ == "__main__":
    process_all_calls()