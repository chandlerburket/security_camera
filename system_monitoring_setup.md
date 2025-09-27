# System Monitoring Setup Instructions

## Overview
This guide explains how to set up comprehensive system monitoring for the security camera that will detect and report failures through Pushover notifications.

## Prerequisites
1. Security camera code deployed to Raspberry Pi Zero W
2. Pushover account configured (pushover_config.py)
3. SSH access to the Pi

## Manual Setup Steps

### 1. Make Scripts Executable
```bash
chmod +x security_cam.py
chmod +x watchdog_monitor.py
```

### 2. Install Required Python Package
```bash
pip3 install psutil
```

### 3. Create Security Camera Service
Create the file `/etc/systemd/system/security-camera.service`:
```ini
[Unit]
Description=Security Camera Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/security_camera
ExecStart=/usr/bin/python3 /home/pi/security_camera/security_cam.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits for Pi Zero W
MemoryMax=200M
CPUQuota=80%

# Environment variables
Environment=PYTHONPATH=/home/pi/security_camera
Environment=PYTHONUNBUFFERED=1

# Restart policies
StartLimitInterval=300
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
```

### 4. Create Watchdog Service
Create the file `/etc/systemd/system/security-camera-watchdog.service`:
```ini
[Unit]
Description=Security Camera Watchdog
After=security-camera.service
Requires=security-camera.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/security_camera
ExecStart=/usr/bin/python3 /home/pi/security_camera/watchdog_monitor.py 60
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

# Restart policies
StartLimitInterval=300
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
```

### 5. Create Shutdown Notification Service
Create the file `/etc/systemd/system/security-camera-shutdown.service`:
```ini
[Unit]
Description=Security Camera Shutdown Notification
DefaultDependencies=false
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
RemainAfterExit=true
ExecStart=/bin/true
ExecStop=/usr/bin/python3 /home/pi/security_camera/send_shutdown_notification.py
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

### 6. Create Shutdown Notification Script
Create the file `/home/pi/security_camera/send_shutdown_notification.py`:
```python
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
        message = f"Security camera system shutting down\\n\\nHostname: {hostname}\\nUptime: {uptime}\\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

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
```

### 7. Make Shutdown Script Executable
```bash
chmod +x /home/pi/security_camera/send_shutdown_notification.py
```

### 8. Add Sudoers Entry for Watchdog
Add this line to `/etc/sudoers.d/security-camera-pi`:
```
pi ALL=(ALL) NOPASSWD: /bin/systemctl restart security-camera
```

### 9. Enable and Start Services
```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable security-camera.service
sudo systemctl enable security-camera-watchdog.service
sudo systemctl enable security-camera-shutdown.service

# Start services
sudo systemctl start security-camera
sudo systemctl start security-camera-watchdog
```

## Service Management Commands

### Check Service Status
```bash
sudo systemctl status security-camera
sudo systemctl status security-camera-watchdog
```

### View Service Logs
```bash
# View current logs
sudo journalctl -u security-camera -f
sudo journalctl -u security-camera-watchdog -f

# View last 50 lines
sudo journalctl -u security-camera -n 50
```

### Start/Stop Services
```bash
# Start services
sudo systemctl start security-camera
sudo systemctl start security-camera-watchdog

# Stop services
sudo systemctl stop security-camera-watchdog
sudo systemctl stop security-camera

# Restart services
sudo systemctl restart security-camera
```

## Monitoring Features

### What Gets Monitored
1. **System Health (every 5 minutes)**:
   - CPU temperature (alerts if > 80°C)
   - Memory usage (alerts if > 90%)
   - Disk space (alerts if > 90%)
   - Camera functionality

2. **Error Tracking**:
   - Automatic error counting
   - Notification after 3+ consecutive errors
   - 15-minute cooldown between error notifications

3. **Service Monitoring**:
   - Watchdog checks main service every 60 seconds
   - Automatic restart on failure
   - Alerts on restart attempts and failures

4. **System Events**:
   - Startup notifications
   - Shutdown notifications
   - Unexpected restart alerts

### Notification Types
- **Startup**: System came online
- **Shutdown**: Planned system shutdown
- **Health Alert**: System resource issues
- **Error Alert**: Multiple errors detected
- **Service Failure**: Main service stopped responding
- **Critical Failure**: Unable to restart service

## Troubleshooting

### Check if Services are Running
```bash
systemctl is-active security-camera
systemctl is-active security-camera-watchdog
```

### View Detailed Service Information
```bash
systemctl show security-camera
```

### Manual Testing
```bash
# Test main service
python3 /home/pi/security_camera/security_cam.py

# Test watchdog
python3 /home/pi/security_camera/watchdog_monitor.py

# Test shutdown notification
python3 /home/pi/security_camera/send_shutdown_notification.py
```

### Common Issues
1. **Pushover not configured**: Check pushover_config.py exists and is valid
2. **Permission errors**: Ensure pi user owns all files
3. **Service won't start**: Check logs with `journalctl -u security-camera`
4. **Watchdog alerts**: Check main service health and system resources

## Security Notes
- Services run as pi user (not root) for security
- Resource limits prevent system overload
- Automatic restart prevents indefinite failure loops
- Sudoers entry limited to specific restart command only