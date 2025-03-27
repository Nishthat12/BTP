#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from kubernetes import client, config

def get_video_server_pods():
    """Get all video server pods"""
    config.load_kube_config()
    v1 = client.CoreV1Api()
    
    pods = v1.list_namespaced_pod(
        namespace="open5gs",
        label_selector="app=video-server"
    )
    
    return [pod.metadata.name for pod in pods.items]

def distribute_blocks():
    """Distribute erasure-coded blocks to video servers"""
    video_servers = get_video_server_pods()
    num_servers = len(video_servers)
    
    if num_servers == 0:
        print("No video server pods found")
        return
    
    print(f"Found {num_servers} video server pods")
    
    # Get all chunks
    chunks = sorted([d for d in os.listdir("coded_chunks") if d.startswith("chunk")])
    
    # Track the assignment of blocks to servers
    assignment = {}
    
    for chunk in chunks:
        chunk_dir = os.path.join("coded_chunks", chunk)
        blocks = sorted([f for f in os.listdir(chunk_dir) if f.startswith("block")])
        
        # Assign each block to a different server
        for i, block in enumerate(blocks):
            server_idx = i % num_servers
            server = video_servers[server_idx]
            
            block_path = os.path.join(chunk_dir, block)
            
            # Copy the block to the server
            copy_cmd = [
                "kubectl", "cp", 
                block_path, 
                f"open5gs/{server}:/usr/local/tomcat/webapps/ROOT/{chunk}_{block}"
            ]
            subprocess.run(copy_cmd)
            
            # Record the assignment
            if server not in assignment:
                assignment[server] = []
            
            assignment[server].append(f"{chunk}_{block}")
            
            print(f"Copied {chunk}/{block} to {server}")
    
    # Save the assignment to a file
    with open("block_assignment.json", "w") as f:
        json.dump(assignment, f, indent=2)
    
    print("Block distribution completed")
    print(f"Assignment saved to block_assignment.json")

def main():
    if not os.path.exists("coded_chunks"):
        print("Error: coded_chunks directory not found. Run encode_video.py first.")
        sys.exit(1)
    
    distribute_blocks()

if __name__ == "__main__":
    main()
