#!/usr/bin/env python3
from flask import Flask, request, Response, jsonify
import requests
import os
import json
import random
import zfec
import numpy as np
import time
import threading
import logging
from ucb_algorithms import L_EMS, D_EMS

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simulated portal server endpoint
PORTAL_SERVER = os.environ.get('PORTAL_SERVER', 'http://portal-server.open5gs.svc.cluster.local')

# Global variables
server_list = []
algorithm_type = os.environ.get('ALGORITHM', 'L_EMS')  # L_EMS or D_EMS
algorithm = None
round_num = 1

def initialize_server_list():
    """Initialize the list of video servers"""
    global server_list, algorithm
    
    try:
        # In a real implementation, this would fetch from the portal server
        with open('/app/block_assignment.json', 'r') as f:
            assignments = json.load(f)
            
        server_list = list(assignments.keys())
        
        # Initialize the selected algorithm
        if algorithm_type == 'L_EMS':
            algorithm = L_EMS(server_list)
        else:
            algorithm = D_EMS(server_list)
        
        logger.info(f"Initialized {algorithm_type} algorithm with {len(server_list)} servers")
    except Exception as e:
        logger.error(f"Error initializing server list: {e}")
        # Fallback to empty list
        pass

@app.route('/proxy/manifest.mpd')
def get_manifest():
    """Serve the MPD manifest"""
    manifest = """<?xml version="1.0" encoding="utf-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" minBufferTime="PT1.500S" type="static" mediaPresentationDuration="PT10M" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011">
  <Period>
    <AdaptationSet segmentAlignment="true" maxWidth="3840" maxHeight="2160" maxFrameRate="30" par="16:9">
      <Representation id="1" mimeType="video/mp4" codecs="avc1.640028" width="3840" height="2160" frameRate="30" sar="1:1" startWithSAP="1" bandwidth="10000000">
        <SegmentList timescale="1000" duration="4000">
"""
    
    # Add segments to the manifest
    num_chunks = 10  # For simplicity, we'll use 10 chunks
    for i in range(num_chunks):
        manifest += f'          <SegmentURL media="/proxy/chunk{i:03d}.mp4" />\n'
    
    manifest += """        </SegmentList>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>"""
    
    return Response(manifest, mimetype='application/dash+xml')

@app.route('/proxy/<chunk_name>.mp4')
def get_chunk(chunk_name):
    """Handle chunk requests using the EMS framework"""
    global round_num
    
    try:
        # Step 1: Select servers using our algorithm
        selected_servers = algorithm.select_servers(round_num)
        
        # Step 2: Download blocks from selected servers
        blocks, metrics = download_blocks(chunk_name, selected_servers)
        
        # Step 3: Decode the blocks to reconstruct the chunk
        chunk_data = decode_blocks(blocks, chunk_name)
        
        # Step 4: Update service quality metrics
        algorithm.update(selected_servers, metrics)
        
        # Increment round number
        round_num += 1
        
        # Return the chunk
        return Response(chunk_data, mimetype='video/mp4')
    except Exception as e:
        logger.error(f"Error serving chunk {chunk_name}: {e}")
        return Response(status=500)

def download_blocks(chunk_name, servers):
    """Download blocks from selected servers
    
    Returns:
        tuple: (blocks, metrics)
            blocks: Dictionary mapping block index to block data
            metrics: Dictionary mapping server to performance metric
    """
    blocks = {}
    metrics = {}
    
    # In a real implementation, we would fetch from actual servers
    # For this simulation, we'll return dummy data
    for i, server in enumerate(servers):
        # Simulate block download with latency
        start_time = time.time()
        time.sleep(random.uniform(0.1, 0.5))  # Simulate network latency
        blocks[i] = b'X' * 1024 * 1024  # 1MB dummy data
        
        # Calculate metrics
        latency = time.time() - start_time
        deadline = 1.0  # 1 second deadline
        
        if algorithm_type == 'L_EMS':
            # Latency-sensitive metric: normalized truncated latency
            normalized_latency = min(latency / deadline, 1.0)
            metrics[server] = normalized_latency
        else:
            # Deadline-aware metric: success indicator
            success = 1 if latency <= deadline else 0
            metrics[server] = success
        
        logger.info(f"Downloaded block {i} from server {server} with latency {latency:.3f}s")
    
    return blocks, metrics

def decode_blocks(blocks, chunk_name):
    """Decode blocks using erasure coding"""
    # In a real implementation, we would use zfec to decode
    # For this simulation, we'll return dummy data
    chunk_data = b''.join(blocks.values())
    logger.info(f"Decoded chunk {chunk_name}")
    
    return chunk_data

# Initialize server list on startup
initialize_server_list()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
