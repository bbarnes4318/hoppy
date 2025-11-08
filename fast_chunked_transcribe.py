import os
import subprocess
import whisper
from datetime import datetime

print("Step 1: Splitting audio into 10-minute chunks...")

# Split the audio into 10-minute chunks
subprocess.run([
    'ffmpeg', '-i', 'input_audio/sherpa_tiny.mp3',
    '-f', 'segment',
    '-segment_time', '600',  # 10 minutes
    '-c', 'copy',
    'input_audio/chunk_%03d.mp3'
], check=True)

print("Step 2: Loading Whisper model (tiny for speed)...")
model = whisper.load_model("tiny")  # Use tiny - it's 39x faster!

# Find all chunks
chunks = sorted([f for f in os.listdir('input_audio') if f.startswith('chunk_')])
print(f"Found {len(chunks)} chunks to process")

# Process each chunk
all_text = []
for i, chunk in enumerate(chunks, 1):
    print(f"Processing chunk {i}/{len(chunks)}: {chunk}")
    
    result = model.transcribe(f'input_audio/{chunk}', language="en", fp16=False)
    all_text.append(result['text'])
    
    # Delete chunk after processing to save space
    os.remove(f'input_audio/{chunk}')
    print(f"  ✓ Done with chunk {i}")

# Combine and save
print("Step 3: Saving transcript...")
os.makedirs('transcripts', exist_ok=True)
output_file = f"transcripts/sherpa_full_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("="*80 + "\n")
    f.write("FULL TRANSCRIPT - video-done-sherpa.mp4\n")
    f.write(f"Generated: {datetime.now()}\n")
    f.write(f"Total chunks processed: {len(chunks)}\n")
    f.write("="*80 + "\n\n")
    
    for i, text in enumerate(all_text, 1):
        f.write(f"\n--- SEGMENT {i} (approx {(i-1)*10}-{i*10} minutes) ---\n")
        f.write(text)
        f.write("\n")

print(f"\n✅ SUCCESS! Transcript saved to: {output_file}")
print(f"Processed {len(chunks)} x 10 minute segments")
