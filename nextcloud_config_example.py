#!/usr/bin/env python3
"""
Nextcloud Configuration Example for Security Camera
Copy this file to 'nextcloud_config.py' and update with your server details
"""

# Nextcloud Server Configuration
NEXTCLOUD_CONFIG = {
    # Your Nextcloud server URL (without trailing slash)
    # Examples:
    #   "http://192.168.1.100:8080"  # Local server with custom port
    #   "https://mycloud.example.com"  # Remote server with SSL
    "url": "http://192.168.1.100",

    # Your Nextcloud username
    "username": "camera_user",

    # Your Nextcloud password or app password
    # Note: Consider using app passwords for better security
    # Go to Settings > Personal > Security > App passwords in Nextcloud
    "password": "your_password_here",

    # Folder where motion-detected images will be saved
    # The folder will be created automatically if it doesn't exist
    "folder": "/motion_captures",

    # Folder where video recordings will be saved
    # The folder will be created automatically if it doesn't exist
    "video_folder": "/recordings",

    # Enable/disable Nextcloud uploads
    "enabled": True,

    # Minimum seconds between image saves (prevents spam)
    "save_interval": 5
}

# How to use this configuration:
# 1. Copy this file to 'nextcloud_config.py'
# 2. Update the values above with your actual Nextcloud server details
# 3. In your main script, import and use like this:
#
#    from nextcloud_config import NEXTCLOUD_CONFIG
#
#    # Configure Nextcloud settings
#    streamer.configure_nextcloud(
#        url=NEXTCLOUD_CONFIG["url"],
#        username=NEXTCLOUD_CONFIG["username"],
#        password=NEXTCLOUD_CONFIG["password"],
#        folder=NEXTCLOUD_CONFIG["folder"],
#        enabled=NEXTCLOUD_CONFIG["enabled"]
#    )
#    streamer.save_interval = NEXTCLOUD_CONFIG["save_interval"]

# Security Notes:
# - Never commit your actual credentials to version control
# - Consider using environment variables for sensitive data
# - Use app passwords instead of your main password when possible
# - Ensure your Nextcloud server is properly secured
