#!/usr/bin/env python3
import os
import subprocess
import json

def get_video_metadata(video_path):
    """Extract metadata such as codec and bitrate from a video file."""
    try:
        # Use ffprobe to extract metadata
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,bit_rate",
                "-of", "json", video_path
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        metadata = json.loads(result.stdout)
        codec_name = metadata['streams'][0].get('codec_name', 'unknown')
        bit_rate = int(metadata['streams'][0].get('bit_rate', 0))
        return codec_name, bit_rate
    except Exception as e:
        print(f"Error extracting metadata for {video_path}: {e}")
        return None, None

def reconstruct_video():
    """Reconstruct the video from decoded chunks while matching original settings."""
    original_video = "sample_video.mp4"
    reconstructed_video = "reconstructed_video.mp4"
    
    # Check if decoded chunks exist
    if not os.path.exists("decoded_chunks"):
        print("Error: 'decoded_chunks' directory not found. Run the decoding step first.")
        return
    
    # Get list of decoded chunks
    chunk_files = sorted([f for f in os.listdir("decoded_chunks") if f.endswith(".mp4")])
    if not chunk_files:
        print("Error: No decoded chunks found in 'decoded_chunks'.")
        return
    
    # Create a file list for FFmpeg
    filelist_path = "filelist.txt"
    try:
        with open(filelist_path, "w") as f:
            for chunk_file in chunk_files:
                f.write(f"file 'decoded_chunks/{chunk_file}'\n")
    except Exception as e:
        print(f"Error creating file list: {e}")
        return
    
    # Extract metadata from the original video
    codec_name, bit_rate = get_video_metadata(original_video)
    if codec_name is None or bit_rate == 0:
        print("Error: Unable to extract codec or bitrate information from the original video.")
        return
    
    print(f"Original Video Codec: {codec_name}, Bitrate: {bit_rate} bps")
    
    # Reconstruct video using FFmpeg with matched settings
    try:
        subprocess.run(
            [
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", filelist_path,
                "-c:v", codec_name, "-b:v", str(bit_rate),  # Match codec and bitrate
                "-c:a", "aac", "-b:a", "128k",  # Match audio settings (if applicable)
                reconstructed_video
            ],
            check=True
        )
        print(f"Reconstructed video saved as '{reconstructed_video}'")
    except subprocess.CalledProcessError as e:
        print(f"Error during video reconstruction: {e}")
    
    # Clean up temporary file list
    try:
        os.remove(filelist_path)
    except Exception as e:
        print(f"Warning: Could not remove temporary file list: {e}")

def main():
    reconstruct_video()

if __name__ == "__main__":
    main()

