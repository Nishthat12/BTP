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

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simulated portal server endpoint (in a real setup, this would be the actual portal server)
PORTAL_SERVER = os.environ.get('PORTAL_SERVER', 'http://portal-server.open5gs.svc.cluster.local')

# Global variables to store service quality metrics
service_quality = {}
selected_servers_history = []

# UCB algorithm parameters
alpha = 1.0  # Exploration parameter

def initialize_service_quality():
    """Initialize service quality metrics for all servers"""
    try:
        # In a real implementation, this would fetch from the portal server
        with open('/app/block_assignment.json', 'r') as f:
            assignments = json.load(f)
            
        for server in assignments.keys():
            service_quality[server] = {
                'theta': 0.5,  # Initial estimate
                'n': 1,        # Number of selections
            }
        
        logger.info(f"Initialized service quality for {len(service_quality)} servers")
    except Exception as e:
        logger.error(f"Error initializing service quality: {e}")
        # Fallback to empty service quality
        pass

@app.route('/proxy/manifest.mpd')
def get_manifest():
    """Serve the MPD manifest"""
    # In a real implementation, this would fetch from the portal server
    # For this simulation, we'll return a static manifest
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
    try:
        # Step 1: Select servers using our algorithm
        selected_servers = select_servers(chunk_name)
        
        # Step 2: Download blocks from selected servers
        blocks = download_blocks(chunk_name, selected_servers)
        
        # Step 3: Decode the blocks to reconstruct the chunk
        chunk_data = decode_blocks(blocks, chunk_name)
        
        # Step 4: Update service quality metrics
        update_service_quality(selected_servers)
        
        # Return the chunk
        return Response(chunk_data, mimetype='video/mp4')
    except Exception as e:
        logger.error(f"Error serving chunk {chunk_name}: {e}")
        return Response(status=500)

def select_servers(chunk_name):
    """Select servers using UCB algorithm"""
    # Number of data blocks needed (k=6 in our erasure coding)
    k = 6
    
    # Calculate UCB scores
    ucb_scores = {}
    for server, metrics in service_quality.items():
        ucb_score = metrics['theta'] + alpha * np.sqrt(np.log(sum(s['n'] for s in service_quality.values())) / metrics['n'])
        ucb_scores[server] = ucb_score
    
    # Select top k servers by UCB score
    selected_servers = sorted(ucb_scores.items(), key=lambda x: x[1], reverse=True)[:k]
    selected_servers = [server for server, _ in selected_servers]
    
    logger.info(f"Selected servers for {chunk_name}: {selected_servers}")
    selected_servers_history.append(selected_servers)
    
    return selected_servers

def download_blocks(chunk_name, servers):
    """Download blocks from selected servers"""
    blocks = {}
    
    # In a real implementation, we would fetch from actual servers
    # For this simulation, we'll return dummy data
    for i, server in enumerate(servers):
        # Simulate block download
        blocks[i] = b'X' * 1024 * 1024  # 1MB dummy data
        logger.info(f"Downloaded block {i} from server {server}")
    
    return blocks

def decode_blocks(blocks, chunk_name):
    """Decode blocks using erasure coding"""
    # In a real implementation, we would use zfec to decode
    # For this simulation, we'll return dummy data
    chunk_data = b''.join(blocks.values())
    logger.info(f"Decoded chunk {chunk_name}")
    
    return chunk_data

def update_service_quality(servers):
    """Update service quality metrics"""
    for server in servers:
        # Simulate success/failure (90% success rate)
        success = random.random() < 0.9
        
        # Update metrics
        if server in service_quality:
            metrics = service_quality[server]
            new_n = metrics['n'] + 1
            new_theta = (metrics['theta'] * metrics['n'] + (1.0 if success else 0.0)) / new_n
            
            service_quality[server] = {
                'theta': new_theta,
                'n': new_n
            }
    
    logger.info("Updated service quality metrics")

# Initialize service quality on startup
initialize_service_quality()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
