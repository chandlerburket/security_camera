# Raspberry Pi Zero W Setup Guide

## System Optimizations for Pi Zero W

### 1. GPU Memory Split
```bash
# Reduce GPU memory to allocate more RAM to system
sudo raspi-config
# Advanced Options > Memory Split > 16
```

### 2. Disable Unnecessary Services
```bash
# Disable Bluetooth if not needed
sudo systemctl disable bluetooth
sudo systemctl disable hciuart

# Disable audio if not needed
sudo systemctl disable alsa-state
```

### 3. Install Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system packages (more efficient than pip on Pi Zero W)
sudo apt install python3-picamera2 python3-flask python3-opencv python3-numpy -y

# Install requests via pip (not available as system package)
pip3 install requests
```

### 4. Performance Configuration
```bash
# Add to /boot/config.txt for better performance
echo "gpu_mem=16" | sudo tee -a /boot/config.txt
echo "arm_freq=1000" | sudo tee -a /boot/config.txt
echo "core_freq=500" | sudo tee -a /boot/config.txt
echo "sdram_freq=500" | sudo tee -a /boot/config.txt
```

### 5. Swap Configuration
```bash
# Increase swap file for motion detection processing
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### 6. Automatic Startup (Optional)
```bash
# Create systemd service
sudo nano /etc/systemd/system/security-camera.service
```

Service file content:
```ini
[Unit]
Description=Security Camera
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/security_camera
ExecStart=/usr/bin/python3 security_cam.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable the service:
```bash
sudo systemctl enable security-camera.service
sudo systemctl start security-camera.service
```

## Key Optimizations Applied

1. **Video Resolution**: Reduced to 320x240 for lower bandwidth and processing
2. **Frame Rate**: Reduced to 15 FPS to decrease CPU load
3. **Motion Detection**: Simplified algorithms and reduced processing intensity
4. **Memory Usage**: Removed unnecessary PIL dependency
5. **Update Intervals**: Increased intervals for status updates and notifications
6. **Processing**: Reduced blur kernels and morphological operations

## Expected Performance
- **Memory Usage**: ~150-200 MB
- **CPU Usage**: 40-60% during streaming with motion detection
- **Network**: ~1-2 Mbps for 320x240 @ 15fps
- **Stability**: Should run continuously without memory leaks

## Troubleshooting
- If camera fails to start, check `vcgencmd get_camera`
- Monitor temperature with `vcgencmd measure_temp`
- Check memory usage with `free -h`
- Monitor CPU with `top` or `htop`