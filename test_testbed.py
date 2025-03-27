#!/usr/bin/env python3
import requests
import time
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_video_client():
    """Test the video client"""
    # Get node IP
    node_ip = "localhost"  # Change this to your node IP if needed
    
    try:
        # Test access to the video player
        response = requests.get(f"http://{node_ip}:30500")
        if response.status_code == 200:
            logger.info("✅ Video client web interface is accessible")
        else:
            logger.error(f"❌ Video client web interface returned status code {response.status_code}")
            return False
        
        # Test access to the manifest
        response = requests.get(f"http://{node_ip}:30500/proxy/manifest.mpd")
        if response.status_code == 200 and "MPD" in response.text:
            logger.info("✅ DASH manifest is accessible")
        else:
            logger.error(f"❌ DASH manifest returned status code {response.status_code}")
            return False
        
        # Test access to a video chunk
        response = requests.get(f"http://{node_ip}:30500/proxy/chunk000.mp4", stream=True)
        if response.status_code == 200:
            # Get the first few bytes
            chunk = next(response.iter_content(chunk_size=1024))
            logger.info(f"✅ Video chunk is accessible (received {len(chunk)} bytes)")
        else:
            logger.error(f"❌ Video chunk returned status code {response.status_code}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"❌ Error testing video client: {e}")
        return False

def test_ueransim_connectivity():
    """Test connectivity from UERANSIM UE to the video client"""
    try:
        # Run curl from the UE pod to test connectivity
        import subprocess
        
        # Get UE pod name
        result = subprocess.run(
            "kubectl get pods -n open5gs | grep ueransim-ue1 | awk '{print }'",
            shell=True, capture_output=True, text=True
        )
        ue_pod = result.stdout.strip()
        
        if not ue_pod:
            logger.error("❌ Could not find UERANSIM UE pod")
            return False
        
        # Test connectivity to video client service
        result = subprocess.run(
            f"kubectl exec -n open5gs {ue_pod} -- curl -s -o /dev/null -w '%{{http_code}}' http://video-client.open5gs.svc.cluster.local",
            shell=True, capture_output=True, text=True
        )
        
        status_code = result.stdout.strip()
        if status_code == "200":
            logger.info("✅ UERANSIM UE can access the video client service")
            return True
        else:
            logger.error(f"❌ UERANSIM UE cannot access the video client service (status code: {status_code})")
            return False
    except Exception as e:
        logger.error(f"❌ Error testing UERANSIM connectivity: {e}")
        return False

def main():
    logger.info("Starting testbed verification...")
    
    # Test video client
    if not test_video_client():
        logger.error("❌ Video client tests failed")
        return 1
    
    # Test UERANSIM connectivity
    if not test_ueransim_connectivity():
        logger.error("❌ UERANSIM connectivity tests failed")
        return 1
    
    logger.info("✅ All tests passed! The testbed is working correctly.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
