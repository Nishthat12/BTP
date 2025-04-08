from flask import Flask, send_file
import requests
from zfec import Decoder
import json
import os

app = Flask(__name__)
K = 4  # Data blocks needed
M = 2  # Parity blocks
TOMCAT_SVC = "tomcat-svc"  # Headless service for Tomcat pods

def decode_chunk(chunk_id):
    # Get available blocks from Tomcat pods
    blocks = []
    for pod_num in range(6):
        try:
            resp = requests.get(
                f"http://{TOMCAT_SVC}-{pod_num}/chunks/{chunk_id}/block{pod_num:02d}.bin",
                timeout=2
            )
            blocks.append((pod_num, resp.content))
        except Exception as e:
            print(f"Failed to get block {pod_num}: {str(e)}")

    if len(blocks) < K:
        return None

    # Decode using first K blocks
    decoder = Decoder(K, K+M)
    indices = [bn for bn, _ in blocks[:K]]
    data_blocks = [bd for _, bd in blocks[:K]]
    
    try:
        decoded = b"".join(decoder.decode(data_blocks, indices))
        metadata = json.loads(requests.get(
            f"http://{TOMCAT_SVC}-0/chunks/{chunk_id}/metadata.json"
        ).content)
        return decoded[:metadata['original_size']]
    except Exception as e:
        print(f"Decode failed: {str(e)}")
        return None

@app.route('/video/<int:chunk_id>.mp4')
def get_chunk(chunk_id):
    decoded = decode_chunk(chunk_id)
    if decoded:
        return (decoded, 200, {
            'Content-Type': 'video/mp4',
            'Access-Control-Allow-Origin': '*'
        })
    return ("Chunk unavailable", 404)

@app.route('/manifest.mpd')
def manifest():
    return send_file('static/manifest.mpd')

