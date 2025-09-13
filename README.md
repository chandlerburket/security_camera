# Raspberry Pi Camera Web Server Setup

## Prerequisites

1. **Raspberry Pi** (3B+ or newer recommended)
2. **Camera Module** (v1, v2, or HQ Camera)
3. **Raspberry Pi OS** with camera support enabled

## Installation Steps

### 1. Enable Camera Support
```bash
# Enable camera interface
sudo raspi-config
# Navigate to: Interface Options > Camera > Enable

# Alternative command-line method:
sudo raspi-config nonint do_camera 0
```

### 2. Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Install Python Dependencies
```bash
# Install required packages
sudo apt install -y python3-pip python3-venv

# Create virtual environment (recommended)
python3 -m venv camera_env
source camera_env/bin/activate

# Install Python packages
pip install flask picamera2 pillow
```

### 4. Install Script
```bash
# Save the Python script as camera_server.py
# Make it executable
chmod +x camera_server.py
```

## Running the Server

### Basic Usage
```bash
# Activate virtual environment
source camera_env/bin/activate

# Run the server
python3 camera_server.py
```

### Run as Background Service
```bash
# Run in background
nohup python3 camera_server.py > camera_server.log 2>&1 &

# Check if running
ps aux | grep camera_server.py
```

### Create Systemd Service (Auto-start on boot)

Create service file:
```bash
sudo nano /etc/systemd/system/camera-server.service
```

Add this content:
```ini
[Unit]
Description=Raspberry Pi Camera Web Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/home/pi/camera_env/bin/python /home/pi/camera_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start service:
```bash
sudo systemctl enable camera-server.service
sudo systemctl start camera-server.service

# Check status
sudo systemctl status camera-server.service
```

## Accessing the Stream

### Local Access
- Open browser: `http://localhost:5000`

### Network Access
```bash
# Find your Pi's IP address
hostname -I
# Then access: http://[PI_IP_ADDRESS]:5000
```

### Port Forwarding (Optional)
To access from outside your network, configure port forwarding on your router:
- External Port: 8080 (or your choice)
- Internal Port: 5000
- Internal IP: Your Pi's IP address

## Configuration Options

### Camera Resolution
Edit the script to change resolution:
```python
config = self.picam2.create_video_configuration(
    main={"size": (1280, 720)},  # Higher resolution
    lores={"size": (640, 480)},  # Streaming resolution
    display="lores"
)
```

### Frame Rate
Adjust the delay in `capture_frames()`:
```python
time.sleep(0.017)  # ~60 FPS (faster)
time.sleep(0.067)  # ~15 FPS (slower, less CPU usage)
```

### Network Port
Change the port in `app.run()`:
```python
app.run(host='0.0.0.0', port=8080)  # Use port 8080 instead
```

## Troubleshooting

### Camera Not Detected
```bash
# Check if camera is detected
vcgencmd get_camera

# Should show: supported=1 detected=1

# If not detected, check physical connection
# Ensure camera ribbon cable is properly seated
```

### Permission Errors
```bash
# Add user to video group
sudo usermod -a -G video $USER

# Reboot to apply changes
sudo reboot
```

### High CPU Usage
- Reduce resolution in camera configuration
- Increase frame delay (lower FPS)
- Use hardware acceleration if available

### Network Issues
```bash
# Check if port is accessible
sudo netstat -tlnp | grep :5000

# Open firewall port if needed
sudo ufw allow 5000
```

## Security Considerations

1. **Change Default Port**: Don't use port 5000 in production
2. **Add Authentication**: Implement login system for sensitive areas
3. **Use HTTPS**: Set up SSL certificates for encrypted streaming
4. **Firewall Rules**: Restrict access to trusted IP addresses
5. **Network Isolation**: Consider using a separate IoT network

## Performance Tips

1. **Use Ethernet**: Wired connection is more stable than WiFi
2. **Quality vs Performance**: Lower JPEG quality reduces bandwidth
3. **Resolution Balance**: Find optimal balance between quality and performance
4. **CPU Monitoring**: Use `htop` to monitor system resources
5. **Storage**: Use fast SD card (Class 10 or better)

## Additional Features

### Motion Detection
Add motion detection using OpenCV:
```bash
pip install opencv-python
```

### Recording
Add video recording functionality by saving frames to files

### Multiple Cameras
Modify script to support multiple camera modules

### Mobile App
Create companion mobile app using the REST API endpoints
