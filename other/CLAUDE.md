# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based call transcription and analysis application for Final Expense (FE) insurance sales. The system processes audio recordings from sales calls, transcribes them using AssemblyAI, and analyzes them using OpenAI GPT models to extract insurance application details.

## Key Dependencies

- Python 3.12.4
- OpenAI API (for GPT-4 analysis)
- AssemblyAI API (for transcription)
- Flask (for web dashboard)
- pydub (for audio processing)
- python-dotenv (for environment variables)

## Environment Variables

The application requires these API keys in a `.env` file:
- `ASSEMBLYAI_API_KEY` - For audio transcription
- `OPENAI_API_KEY` - For transcript analysis

## Common Commands

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Main Application
```bash
python app.py
```

### Run Dashboard
```bash
python dashboard.py
```

### Activate Virtual Environment
```bash
# Windows PowerShell
.\Scripts\Activate.ps1

# Windows Command Prompt
Scripts\activate.bat

# Unix/MacOS
source Scripts/activate
```

## Architecture Overview

### Core Processing Flow
1. **Audio Download**: Downloads MP3 files from URLs (stored in `urls.txt`)
2. **Transcription**: Uploads audio to AssemblyAI API for speech-to-text
3. **Analysis**: Uses OpenAI GPT-4 to analyze transcripts for insurance application details
4. **Data Extraction**: Extracts customer information, policy details, payment info

### Key Components

- **app.py**: Main application for batch processing URLs
- **dashboard.py**: Flask web dashboard for real-time call monitoring
- **Multiple specialized analyzers**: Various `aca-*.py`, `fe*.py` files for different insurance products (ACA, Final Expense)
- **Audio Storage**: 
  - `downloaded_audio_files/` - Original recordings
  - `transcriptions/` - Text transcripts
  - `analysis_results/` - GPT analysis outputs

### Data Processing Pipeline

The application processes insurance sales calls to determine:
- Application submission status
- Customer details (name, address, DOB, SSN)
- Policy information (coverage amount, premium, carrier)
- Payment information (bank routing/account, credit card)
- Agent performance metrics

### Output Formats
- Individual transcript files in `transcriptions/`
- Combined analysis results in `results/`
- CSV exports for sales data (`aca_sales.csv`, `petepete.csv`)

## Important Notes

- The application handles sensitive customer data including SSN, bank accounts, and credit cards
- Multiple virtual environments exist (`venv/`, `fe_venv/`, `venv_name/`) - use `Scripts/` for activation
- FFmpeg is included locally in `ffmpeg/` directory for audio processing
- Ringba API integration available for real-time call processing (API key hardcoded in dashboard.py)