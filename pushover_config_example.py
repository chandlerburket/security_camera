"""
Pushover Configuration Example

To enable Pushover notifications:
1. Copy this file to pushover_config.py
2. Sign up for a Pushover account at https://pushover.net/
3. Create an application at https://pushover.net/apps/build
4. Update the configuration below with your credentials
5. Set enabled=True

Your user key can be found at: https://pushover.net/
Your application token is generated when you create an app.
"""

PUSHOVER_CONFIG = {
    "enabled": False,  # Set to True to enable Pushover notifications
    "user_key": "your_pushover_user_key_here",  # Your 30-character user key
    "api_token": "your_pushover_api_token_here",  # Your application's API token
    "notify_interval": 60,  # Minimum seconds between notifications (default: 60)
}