#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import json
from zfec import easyfec

def download_sample_video():
    """Download a sample video if not already present"""
    if not os.path.exists("sample_video.mp4"):
        print("Downloading sample video...")
        subprocess.run(["wget", "-O", "sample_video.mp4", 
                       "https://download.samplelib.com/4k/sample-video-3840x2160.mp4"])
    else:
        print("Sample video already exists")

def segment_video():
    """Segment the video into chunks"""
    if not os.path.exists("chunks"):
        os.makedirs("chunks")
    
    # Use FFmpeg to segment the video into 4-second chunks
    subprocess.run(["ffmpeg", "-i", "sample_video.mp4", "-c", "copy", 
                   "-map", "0", "-segment_time", "4", "-f", "segment", 
                   "chunks/chunk%03d.mp4"])
    
    print("Video segmented into chunks")

def erasure_code_chunks(k=6, m=6):
    """Apply erasure coding to each chunk"""
    from zfec import Encoder
    
    encoder = Encoder(k, k + m)
    
    if not os.path.exists("coded_chunks"):
        os.makedirs("coded_chunks")

    chunks = sorted([f for f in os.listdir("chunks") if f.startswith("chunk")])
    
    for chunk in chunks:
        chunk_path = os.path.join("chunks", chunk)
        
        with open(chunk_path, "rb") as f:
            data = f.read()

        # Calculate required padding
        padding = (-len(data)) % k
        padded_data = data + b'\x00' * padding

        # Verify divisible by k
        if len(padded_data) % k != 0:
            raise ValueError(f"Padded data length {len(padded_data)} not divisible by k={k}")

        # Split into k equal segments
        segment_size = len(padded_data) // k
        segments = [
            padded_data[i*segment_size : (i+1)*segment_size]
            for i in range(k)
        ]

        # Encode using zfec's native interface
        encoded_blocks = encoder.encode(segments)

        # Save blocks
        chunk_name = os.path.splitext(chunk)[0]
        chunk_dir = os.path.join("coded_chunks", chunk_name)
        os.makedirs(chunk_dir, exist_ok=True)
        
        for i, block in enumerate(encoded_blocks):
            with open(os.path.join(chunk_dir, f"block{i:02d}.bin"), "wb") as f:
                f.write(block)

        # Save metadata
        metadata = {
            'original_size': len(data),
            'padding_size': padding,
            'k': k,
            'm': m
        }
        with open(os.path.join(chunk_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f)
        
        print(f"Erasure-coded {chunk}")


def main():
    download_sample_video()
    segment_video()
    erasure_code_chunks()
    print("Video processing completed")

if __name__ == "__main__":
    main()
