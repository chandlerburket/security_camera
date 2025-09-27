#!/bin/bash
# Installation script for security camera services

set -e

echo "🔧 Installing Security Camera Services..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root. Run as regular user (pi)."
   exit 1
fi

# Get the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER=$(whoami)

echo "📁 Installing from: $SCRIPT_DIR"
echo "👤 User: $USER"

# Create systemd service for main security camera
echo "📝 Creating security camera service..."
sudo tee /etc/systemd/system/security-camera.service > /dev/null <<EOF
[Unit]
Description=Security Camera Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/security_cam.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits for Pi Zero W
MemoryMax=200M
CPUQuota=80%

# Environment variables
Environment=PYTHONPATH=$SCRIPT_DIR
Environment=PYTHONUNBUFFERED=1

# Restart policies
StartLimitInterval=300
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for watchdog
echo "📝 Creating watchdog service..."
sudo tee /etc/systemd/system/security-camera-watchdog.service > /dev/null <<EOF
[Unit]
Description=Security Camera Watchdog
After=security-camera.service
Requires=security-camera.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/watchdog_monitor.py 60
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

# Restart policies
StartLimitInterval=300
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
EOF

# Create shutdown notification script
echo "📝 Creating shutdown notification script..."
sudo tee /etc/systemd/system/security-camera-shutdown.service > /dev/null <<EOF
[Unit]
Description=Security Camera Shutdown Notification
DefaultDependencies=false
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
RemainAfterExit=true
ExecStart=/bin/true
ExecStop=/usr/bin/python3 $SCRIPT_DIR/send_shutdown_notification.py
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create the shutdown notification script
echo "📝 Creating shutdown notification script..."
cat > "$SCRIPT_DIR/send_shutdown_notification.py" <<'EOF'
#!/usr/bin/env python3
"""Send shutdown notification"""

import time
import requests
import socket
from datetime import datetime, timedelta

def send_shutdown_notification():
    try:
        # Load Pushover config
        from pushover_config import PUSHOVER_CONFIG

        if not PUSHOVER_CONFIG["enabled"]:
            return

        # Calculate uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            uptime = timedelta(seconds=int(uptime_seconds))

        hostname = socket.gethostname()
        message = f"Security camera system shutting down\n\nHostname: {hostname}\nUptime: {uptime}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        data = {
            'token': PUSHOVER_CONFIG["api_token"],
            'user': PUSHOVER_CONFIG["user_key"],
            'message': message,
            'title': "System Shutdown",
            'priority': 1
        }

        requests.post(
            "https://api.pushover.net/1/messages.json",
            data=data,
            timeout=10
        )

    except Exception as e:
        print(f"Failed to send shutdown notification: {e}")

if __name__ == "__main__":
    send_shutdown_notification()
EOF

chmod +x "$SCRIPT_DIR/send_shutdown_notification.py"

# Make scripts executable
chmod +x "$SCRIPT_DIR/security_cam.py"
chmod +x "$SCRIPT_DIR/watchdog_monitor.py"

# Add sudoers entry for service restart (for watchdog)
echo "🔐 Adding sudoers entry for service restart..."
echo "$USER ALL=(ALL) NOPASSWD: /bin/systemctl restart security-camera" | sudo tee "/etc/sudoers.d/security-camera-$USER" > /dev/null

# Reload systemd and enable services
echo "🔄 Reloading systemd and enabling services..."
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable security-camera.service
sudo systemctl enable security-camera-watchdog.service
sudo systemctl enable security-camera-shutdown.service

echo "✅ Services installed successfully!"
echo ""
echo "📋 Available commands:"
echo "  sudo systemctl start security-camera     # Start the camera service"
echo "  sudo systemctl stop security-camera      # Stop the camera service"
echo "  sudo systemctl status security-camera    # Check service status"
echo "  sudo journalctl -u security-camera -f    # View service logs"
echo ""
echo "  sudo systemctl start security-camera-watchdog   # Start watchdog"
echo "  sudo systemctl status security-camera-watchdog  # Check watchdog status"
echo ""
echo "🚀 To start the services now:"
echo "  sudo systemctl start security-camera"
echo "  sudo systemctl start security-camera-watchdog"
echo ""
echo "⚠️  Note: Make sure to configure pushover_config.py for notifications!"