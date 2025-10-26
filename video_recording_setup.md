# Video Recording Setup Guide

## Overview
The security camera now includes on-demand video recording functionality with web interface controls. Videos are automatically saved to Nextcloud in a separate directory.

## New Features Added

### 1. Web Interface Controls
- **Red "Start Recording" button**: Begins video recording
- **Green "Stop Recording" button**: Stops recording and saves video
- **Recording status indicator**: Shows current recording state
- **Live recording timer**: Displays recording duration

### 2. Recording Functionality
- **Frame capture**: Records at 5 FPS (optimized for Pi Zero W)
- **Maximum duration**: 5 minutes per recording (Pi Zero W limitation)
- **Auto-stop**: Recordings automatically stop at max duration
- **Memory optimization**: Stores every 3rd frame to reduce memory usage

### 3. Video Processing
- **Format**: MP4 videos using H.264 codec
- **Encoding**: Ultra-fast preset for Pi Zero W performance
- **Quality**: Balanced quality/size ratio (CRF 28)
- **Frame rate**: 5 FPS output for smaller file sizes

### 4. Storage Integration
- **Separate directory**: Videos saved to `/recordings` folder in Nextcloud
- **Automatic upload**: Videos uploaded immediately after recording stops
- **Naming convention**: `recording_YYYYMMDD_HHMMSS.mp4`

## Prerequisites

### 1. Install FFmpeg
```bash
sudo apt update
sudo apt install ffmpeg
```

### 2. Install Python Dependencies
```bash
pip3 install psutil
```

### 3. Update Nextcloud Configuration
Add video folder to your `nextcloud_config.py`:
```python
NEXTCLOUD_CONFIG = {
    "url": "http://192.168.1.100",
    "username": "camera_user",
    "password": "your_password",
    "folder": "/motion_captures",     # For motion detection images
    "video_folder": "/recordings",    # For video recordings
    "enabled": True,
    "save_interval": 10
}
```

## How to Use

### Web Interface
1. **Access camera web page**: `http://[pi-ip]:5000`
2. **Start recording**: Click the red "🔴 Start Recording" button
3. **Monitor progress**: Watch the recording timer and status indicator
4. **Stop recording**: Click the green "⏹️ Stop Recording" button
5. **Confirmation**: You'll see a success message when video is saved

### API Endpoints
- `POST /start-recording` - Start recording
- `POST /stop-recording` - Stop recording and save
- `GET /recording-status` - Get current recording status

### Status Indicators
- **Recording Status Light**:
  - Red: Currently recording
  - Gray: Not recording
- **Recording Banner**: Shows when active with live timer
- **Button States**: Start button disabled during recording

## Technical Details

### Performance Optimizations for Pi Zero W
1. **Low frame rate**: 5 FPS recording to reduce CPU load
2. **Frame skipping**: Only saves every 3rd frame to memory
3. **Fast encoding**: Ultra-fast FFmpeg preset
4. **Memory limits**: Auto-stop at 5 minutes to prevent overflow
5. **Efficient upload**: Immediate upload and cleanup after recording

### File Structure
```
Nextcloud/
├── motion_captures/          # Motion detection images
│   ├── motion_20240101_120000.jpg
│   └── motion_20240101_120030.jpg
└── recordings/               # Video recordings
    ├── recording_20240101_120000.mp4
    └── recording_20240101_120500.mp4
```

### Recording Quality Settings
- **Resolution**: 320x240 (same as stream)
- **Frame rate**: 5 FPS output
- **Codec**: H.264 with YUV420P pixel format
- **Bitrate**: Variable (CRF 28)
- **File size**: ~1-2 MB per minute typical

## Troubleshooting

### Common Issues

1. **FFmpeg not found**
   ```bash
   sudo apt install ffmpeg
   ```

2. **Recording fails to start**
   - Check camera is not already recording
   - Verify sufficient memory available
   - Check logs: `sudo journalctl -u security-camera -f`

3. **Video upload fails**
   - Verify Nextcloud configuration
   - Check network connectivity
   - Ensure `/recordings` folder exists in Nextcloud

4. **Poor video quality**
   - Quality optimized for Pi Zero W performance
   - Higher quality would require more powerful hardware

### Monitoring
- **System logs**: `sudo journalctl -u security-camera -f`
- **Recording status**: Check web interface status indicators
- **Memory usage**: Monitor during recording sessions

### Limitations on Pi Zero W
- **Maximum recording time**: 5 minutes
- **Frame rate**: Limited to 5 FPS for stability
- **Concurrent operations**: May affect motion detection performance
- **Memory usage**: ~50-100 MB during recording

## Security Notes
- Videos stored in separate Nextcloud directory
- No local storage to prevent SD card filling
- Automatic cleanup after upload
- Recording status visible to all web interface users

## Future Enhancements
- Configurable recording quality levels
- Motion-triggered automatic recording
- Recording schedule functionality
- Multiple concurrent recordings (with more powerful hardware)