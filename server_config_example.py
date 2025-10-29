#!/usr/bin/env python3
"""
Server Configuration for Camera Client
Copy this file to 'server_config.py' and update with your server details
"""

SERVER_CONFIG = {
    # URL of the web server where camera will send data
    # This should be the IP or hostname of the machine running web_server.py
    # Examples:
    #   "http://192.168.1.100:5000"  # Local server
    #   "https://camera.example.com"  # Remote server with SSL
    "server_url": "http://192.168.1.100:5000",

    # Unique identifier for this camera
    # If you have multiple cameras, give each one a unique ID
    # Examples: "camera1", "front_door", "backyard", etc.
    "camera_id": "camera1",
}

# How to use this configuration:
# 1. Copy this file to 'server_config.py'
# 2. Update the server_url with your web server's address
# 3. If using multiple cameras, give each a unique camera_id
# 4. The camera client will automatically import and use these settings

# Architecture Notes:
# - The camera_client.py runs on the Pi Zero W (camera device)
# - The web_server.py runs on a separate machine (server)
# - The camera sends video frames and status to the server
# - The server hosts the web interface and controls the camera

# Network Requirements:
# - Camera must be able to reach server on the network
# - Server port (default 5000) must be accessible from camera
# - For external access, configure port forwarding on server
