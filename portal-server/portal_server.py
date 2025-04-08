import os
import json
import numpy as np
import hashlib
import time
import subprocess
from datetime import datetime
import requests
import kubernetes as k8s
from kubernetes import client, config
from pymongo import MongoClient

class PortalServer:
    def __init__(self, storage_path="/app/storage", 
                 data_blocks=6, parity_blocks=2):
        """
        Initialize the Portal Server
        
        Args:
            storage_path: Path to store video metadata
            data_blocks: Number of data blocks per video chunk (D)
            parity_blocks: Number of parity blocks per video chunk (P)
        """
        self.storage_path = storage_path
        self.data_blocks = data_blocks  # D in the paper
        self.parity_blocks = parity_blocks  # P in the paper
        self.metadata_db = {}
        
        # Create storage directory if it doesn't exist
        os.makedirs(storage_path, exist_ok=True)
        os.makedirs(os.path.join(storage_path, "chunks"), exist_ok=True)
        os.makedirs(os.path.join(storage_path, "metadata"), exist_ok=True)
        
        # Connect to MongoDB for storing metadata
        self.mongo_client = MongoClient('mongodb.open5gs.svc.cluster.local:27017')
        self.db = self.mongo_client.videos
        
        # Initialize Kubernetes client for pod discovery
        try:
            config.load_incluster_config()  # Inside cluster
        except:
            config.load_kube_config()  # Local development
        
        self.k8s_client = client.CoreV1Api()
        
        print(f"Portal Server initialized with {data_blocks} data blocks and {parity_blocks} parity blocks")
    
    def discover_video_servers(self):
        """
        Discover available video servers in the Kubernetes cluster
        
        Returns:
            List of video server names and their IPs
        """
        servers = []
        try:
            pods = self.k8s_client.list_namespaced_pod(
                namespace='open5gs',
                label_selector='app=video-server'
            )
            
            for pod in pods.items:
                name = pod.metadata.name
                ip = pod.status.pod_ip
                servers.append({"name": name, "ip": ip})
                
            print(f"Found {len(servers)} video servers")
        except Exception as e:
            print(f"Error discovering video servers: {e}")
        
        return servers
    
    def chunk_video(self, video_path, chunk_duration=4):
        """
        Split a video into fixed-duration chunks
        
        Args:
            video_path: Path to the video file
            chunk_duration: Duration of each chunk in seconds
            
        Returns:
            List of chunk paths
        """
        print(f"Chunking video {video_path} into {chunk_duration}-second chunks")
        
        video_name = os.path.basename(video_path).split('.')[0]
        output_pattern = os.path.join(self.storage_path, "chunks", f"{video_name}_chunk_%03d.mp4")
        
        # Use FFmpeg to split the video into chunks
        command = [
            'ffmpeg', '-i', video_path, 
            '-c', 'copy', '-map', '0',
            '-segment_time', str(chunk_duration),
            '-f', 'segment', output_pattern
        ]
        
        subprocess.run(command, check=True)
        
        # Get list of created chunks
        chunks = []
        chunk_dir = os.path.join(self.storage_path, "chunks")
        for file in os.listdir(chunk_dir):
            if file.startswith(f"{video_name}_chunk_") and file.endswith(".mp4"):
                chunks.append(os.path.join(chunk_dir, file))
        
        chunks.sort()  # Ensure chunks are in order
        print(f"Video chunked into {len(chunks)} parts")
        return chunks
    
    def erasure_code_chunk(self, chunk_path):
        """
        Apply erasure coding to a video chunk using pyfeclib
        
        Args:
            chunk_path: Path to the video chunk
            
        Returns:
            List of paths to the erasure-coded blocks
        """
        import pyfeclib
        
        chunk_name = os.path.basename(chunk_path).split('.')[0]
        print(f"Applying erasure coding to chunk {chunk_name}")
        
        # Read the chunk data
        with open(chunk_path, 'rb') as f:
            data = f.read()
        
        # Apply erasure coding
        encoder = pyfeclib.Encoder(self.data_blocks, self.parity_blocks)
        encoded_blocks = encoder.encode(data)
        
        # Save the encoded blocks
        blocks = []
        for i, block_data in enumerate(encoded_blocks):
            block_type = "data" if i < self.data_blocks else "parity"
            block_path = os.path.join(
                self.storage_path, "chunks", 
                f"{chunk_name}_{block_type}_{i:02d}.block"
            )
            
            with open(block_path, 'wb') as f:
                f.write(block_data)
            
            blocks.append(block_path)
        
        print(f"Chunk erasure-coded into {len(blocks)} blocks "
              f"({self.data_blocks} data, {self.parity_blocks} parity)")
        return blocks
    
    def assign_blocks_to_servers(self, video_id, block_paths):
        """
        Assign blocks to video servers
        
        Args:
            video_id: ID of the video
            block_paths: List of paths to erasure-coded blocks
            
        Returns:
            Dictionary mapping server IDs to assigned blocks
        """
        print(f"Assigning blocks for video {video_id} to video servers")
        
        # Get available video servers
        servers = self.discover_video_servers()
        if not servers:
            raise Exception("No video servers found")
        
        # Group blocks by chunk to ensure blocks from same chunk go to different servers
        blocks_by_chunk = {}
        for block_path in block_paths:
            chunk_id = os.path.basename(block_path).split('_')[0:2]
            chunk_id = '_'.join(chunk_id)
            
            if chunk_id not in blocks_by_chunk:
                blocks_by_chunk[chunk_id] = []
            
            blocks_by_chunk[chunk_id].append(block_path)
        
        # Assign blocks to servers ensuring distribution
        server_assignments = {server["name"]: [] for server in servers}
        server_list = [server["name"] for server in servers]
        
        # Distribute blocks from each chunk to different servers
        for chunk_id, chunk_blocks in blocks_by_chunk.items():
            for i, block in enumerate(chunk_blocks):
                server_id = server_list[i % len(server_list)]
                server_assignments[server_id].append(block)
                
                # Upload the block to the server
                self.upload_block_to_server(block, server_id, servers)
        
        print(f"Blocks assigned to {len(server_assignments)} servers")
        return server_assignments
    
    def upload_block_to_server(self, block_path, server_id, servers):
        """
        Upload a block to a video server
        
        Args:
            block_path: Path to the block file
            server_id: ID of the server
            servers: List of server information
        """
        # Find the server IP
        server_ip = None
        for server in servers:
            if server["name"] == server_id:
                server_ip = server["ip"]
                break
        
        if not server_ip:
            print(f"Server {server_id} not found")
            return
        
        # In a real implementation, this would upload the block to the server
        # For now, just simulate the upload
        print(f"Uploading block {os.path.basename(block_path)} to server {server_id} ({server_ip})")
        
        # Actual implementation would use requests to post the file:
        # with open(block_path, 'rb') as f:
        #     requests.post(f"http://{server_ip}:8080/upload", files={"file": f})
    
    def create_video_metadata(self, video_id, video_path, chunks, server_assignments):
        """
        Create metadata for a video
        
        Args:
            video_id: ID of the video
            video_path: Path to the original video
            chunks: List of chunk paths
            server_assignments: Dictionary mapping server IDs to assigned blocks
            
        Returns:
            Metadata dictionary
        """
        print(f"Creating metadata for video {video_id}")
        
        # Create metadata for each chunk
        chunk_metadata = []
        for chunk_path in chunks:
            chunk_name = os.path.basename(chunk_path).split('.')[0]
            chunk_info = {
                "name": chunk_name,
                "path": chunk_path,
                "duration": 4,  # seconds
                "blocks": []
            }
            
            # Find blocks for this chunk
            for server_id, blocks in server_assignments.items():
                for block in blocks:
                    if chunk_name in block:
                        block_type = "data" if "data" in block else "parity"
                        block_index = int(block.split('_')[-1].split('.')[0])
                        
                        chunk_info["blocks"].append({
                            "path": block,
                            "type": block_type,
                            "index": block_index,
                            "server_id": server_id
                        })
            
            chunk_metadata.append(chunk_info)
        
        # Create the full metadata
        metadata = {
            "video_id": video_id,
            "name": os.path.basename(video_path),
            "created_at": datetime.now().isoformat(),
            "total_chunks": len(chunks),
            "erasure_coding": {
                "data_blocks": self.data_blocks,
                "parity_blocks": self.parity_blocks
            },
            "chunks": chunk_metadata,
            "server_assignments": {k: [os.path.basename(b) for b in v] 
                                  for k, v in server_assignments.items()}
        }
        
        # Save metadata to MongoDB
        self.db.metadata.insert_one(metadata)
        
        # Also save metadata to file
        metadata_path = os.path.join(self.storage_path, "metadata", f"{video_id}.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Metadata created and saved")
        return metadata
    
    def process_video(self, video_path):
        """
        Process a video: chunk, erasure-code, assign to servers, and create metadata
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Video ID and metadata
        """
        print(f"Processing video: {video_path}")
        
        # Generate a video ID
        video_id = hashlib.md5(f"{video_path}_{time.time()}".encode()).hexdigest()[:12]
        
        # Step 1: Chunk the video
        chunks = self.chunk_video(video_path)
        
        # Step 2: Apply erasure coding to each chunk
        all_blocks = []
        for chunk_path in chunks:
            blocks = self.erasure_code_chunk(chunk_path)
            all_blocks.extend(blocks)
        
        # Step 3: Assign blocks to servers
        server_assignments = self.assign_blocks_to_servers(video_id, all_blocks)
        
        # Step 4: Create metadata
        metadata = self.create_video_metadata(video_id, video_path, chunks, server_assignments)
        
        print(f"Video processing complete. Video ID: {video_id}")
        return video_id, metadata
    
    def get_video_metadata(self, video_id):
        """
        Get metadata for a video
        
        Args:
            video_id: ID of the video
            
        Returns:
            Metadata dictionary
        """
        metadata = self.db.metadata.find_one({"video_id": video_id})
        return metadata
    
    def get_server_quality(self, user_area):
        """
        Get service quality indicators for video servers in a user area
        
        Args:
            user_area: User area identifier
            
        Returns:
            Dictionary mapping server IDs to quality indicators
        """
        quality = self.db.server_quality.find_one({"user_area": user_area})
        if not quality:
            # Initialize with default values
            servers = self.discover_video_servers()
            quality = {
                "user_area": user_area,
                "global_indicators": {
                    server["name"]: {
                        "deadline_aware": 0.5,
                        "latency_sensitive": 0.5
                    } for server in servers
                },
                "round": 0
            }
            self.db.server_quality.insert_one(quality)
        
        return quality["global_indicators"]
    
    def update_server_quality(self, user_area, server_id, local_indicators):
        """
        Update service quality indicators for a video server
        
        Args:
            user_area: User area identifier
            server_id: Server ID
            local_indicators: Dictionary with local quality indicators
        """
        quality = self.db.server_quality.find_one({"user_area": user_area})
        if not quality:
            return
        
        # Simple weighted average for global aggregation
        current_round = quality["round"]
        global_indicators = quality["global_indicators"]
        
        if server_id not in global_indicators:
            global_indicators[server_id] = local_indicators
        else:
            for indicator_type, value in local_indicators.items():
                current_value = global_indicators[server_id][indicator_type]
                # Update with simple weighted average
                global_indicators[server_id][indicator_type] = (
                    (current_value * current_round + value) / (current_round + 1)
                )
        
        # Update in MongoDB
        self.db.server_quality.update_one(
            {"user_area": user_area},
            {
                "": {
                    "global_indicators": global_indicators,
                    "round": current_round + 1
                }
            }
        )
    
    def start_server(self):
        """
        Start the portal server with a simple API
        """
        from flask import Flask, request, jsonify
        
        app = Flask(__name__)
        
        @app.route('/process_video', methods=['POST'])
        def api_process_video():
            if 'video' not in request.files:
                return jsonify({"error": "No video file provided"}), 400
            
            video_file = request.files['video']
            video_path = os.path.join(self.storage_path, video_file.filename)
            video_file.save(video_path)
            
            video_id, metadata = self.process_video(video_path)
            return jsonify({"video_id": video_id, "metadata": metadata})
        
        @app.route('/video/<video_id>', methods=['GET'])
        def api_get_video_metadata(video_id):
            metadata = self.get_video_metadata(video_id)
            if not metadata:
                return jsonify({"error": "Video not found"}), 404
            
            return jsonify(metadata)
        
        @app.route('/server_quality/<user_area>', methods=['GET'])
        def api_get_server_quality(user_area):
            quality = self.get_server_quality(user_area)
            return jsonify(quality)
        
        @app.route('/server_quality/<user_area>/<server_id>', methods=['POST'])
        def api_update_server_quality(user_area, server_id):
            local_indicators = request.json
            self.update_server_quality(user_area, server_id, local_indicators)
            return jsonify({"status": "success"})
        
        app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    portal = PortalServer()
    portal.start_server()
