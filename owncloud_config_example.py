#!/usr/bin/env python3
"""
OwnCloud Configuration Example for Security Camera
Copy this file to 'owncloud_config.py' and update with your server details
"""

# OwnCloud Server Configuration
OWNCLOUD_CONFIG = {
    # Your OwnCloud server URL (without trailing slash)
    # Examples:
    #   "http://192.168.1.100:8080"  # Local server with custom port
    #   "https://mycloud.example.com"  # Remote server with SSL
    "url": "http://192.168.1.100",

    # Your OwnCloud username
    "username": "camera_user",

    # Your OwnCloud password or app password
    # Note: Consider using app passwords for better security
    # Go to Settings > Personal > Security > App passwords in OwnCloud
    "password": "your_password_here",

    # Folder where motion-detected images will be saved
    # The folder will be created automatically if it doesn't exist
    "folder": "/motion_captures",

    # Enable/disable OwnCloud uploads
    "enabled": True,

    # Minimum seconds between image saves (prevents spam)
    "save_interval": 5
}

# How to use this configuration:
# 1. Copy this file to 'owncloud_config.py'
# 2. Update the values above with your actual OwnCloud server details
# 3. In your main script, import and use like this:
#
#    from owncloud_config import OWNCLOUD_CONFIG
#
#    # Configure OwnCloud settings
#    streamer.configure_owncloud(
#        url=OWNCLOUD_CONFIG["url"],
#        username=OWNCLOUD_CONFIG["username"],
#        password=OWNCLOUD_CONFIG["password"],
#        folder=OWNCLOUD_CONFIG["folder"],
#        enabled=OWNCLOUD_CONFIG["enabled"]
#    )
#    streamer.save_interval = OWNCLOUD_CONFIG["save_interval"]

# Security Notes:
# - Never commit your actual credentials to version control
# - Consider using environment variables for sensitive data
# - Use app passwords instead of your main password when possible
# - Ensure your OwnCloud server is properly secured