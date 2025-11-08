import os
import whisper
from datetime import datetime

# Load model
print("Loading Whisper...")
model = whisper.load_model("tiny")  # Use tiny for speed

# Process file
input_file = "input_audio/sherpa_tiny.mp3"
print(f"Transcribing {input_file}...")

# Transcribe
result = model.transcribe(input_file, language="en", fp16=False)

# Save transcript
output_file = f"transcripts/sherpa_transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
os.makedirs("transcripts", exist_ok=True)

with open(output_file, "w", encoding="utf-8") as f:
    f.write("="*80 + "\n")
    f.write(f"Transcript of: {input_file}\n")
    f.write(f"Generated: {datetime.now()}\n")
    f.write("="*80 + "\n\n")
    
    # Write segments with timestamps
    for segment in result["segments"]:
        start = segment["start"]
        end = segment["end"]
        text = segment["text"].strip()
        
        # Format timestamp
        start_min = int(start // 60)
        start_sec = int(start % 60)
        
        f.write(f"[{start_min:02d}:{start_sec:02d}] {text}\n")
    
    f.write("\n" + "="*80 + "\n")
    f.write("FULL TEXT:\n")
    f.write("="*80 + "\n")
    f.write(result["text"])

print(f"✅ Saved to {output_file}")
print(f"Total duration: {result['segments'][-1]['end']/60:.1f} minutes")
print(f"Segments: {len(result['segments'])}")
