# Nextcloud Integration Setup Guide

This security camera system can automatically save images to a Nextcloud server when motion is detected.

## Prerequisites

1. **Nextcloud Server**: You need a Nextcloud server running on your local network
2. **Python requests library**: `pip install requests` (usually already installed)
3. **Network access**: Your camera device must be able to reach your Nextcloud server

## Setup Instructions

### 1. Configure Nextcloud Server

Ensure your Nextcloud server is accessible on your local network. You can test this by accessing the web interface from your camera device.

### 2. Create Nextcloud User (Recommended)

For security, create a dedicated user account for the camera:

1. Log into your Nextcloud web interface as admin
2. Go to Users section
3. Create a new user (e.g., `camera_user`)
4. Set a strong password
5. Optionally, create an app password for better security:
   - Go to Settings > Personal > Security > App passwords
   - Create a new app password for "Security Camera"

### 3. Create Upload Folder

1. Log in as your camera user
2. Create a folder called `motion_captures` (or any name you prefer)
3. Note the full path (e.g., `/motion_captures`)

### 4. Configure the Camera System

1. Copy the configuration template:
   ```bash
   cp nextcloud_config_example.py nextcloud_config.py
   ```

2. Edit `nextcloud_config.py` with your settings:
   ```python
   NEXTCLOUD_CONFIG = {
       "url": "http://192.168.1.100:8080",  # Your Nextcloud server URL
       "username": "camera_user",           # Your Nextcloud username
       "password": "your_app_password",     # Your password or app password
       "folder": "/motion_captures",        # Folder to save images
       "enabled": True,                     # Enable uploads
       "save_interval": 5                   # Seconds between saves
   }
   ```

3. Update the values:
   - **url**: Your Nextcloud server IP and port (without trailing slash)
   - **username**: The Nextcloud username you created
   - **password**: The password or app password
   - **folder**: The folder where images will be saved (with leading slash)

## Testing the Setup

### 1. Test Nextcloud Connection

Start your camera system and visit: `http://your-camera-ip:5000/test-nextcloud`

This will test the connection and show you if everything is working.

### 2. Test Motion Detection

1. Start the camera system: `python security_cam.py`
2. Move in front of the camera
3. Check your Nextcloud folder for new images
4. Monitor the console for upload messages

## Image Naming

Images are automatically named with timestamps:
- Format: `motion_YYYYMMDD_HHMMSS.jpg`
- Example: `motion_20250921_143052.jpg`

## Troubleshooting

### Common Issues

1. **"Connection refused" error**
   - Check if Nextcloud server is running
   - Verify the IP address and port
   - Test browser access to Nextcloud

2. **Authentication failed**
   - Verify username and password
   - Try creating an app password instead
   - Check user permissions in Nextcloud

3. **Folder not found**
   - Ensure the folder exists in Nextcloud
   - Check folder path starts with `/`
   - Verify user has write permissions

4. **Images not uploading**
   - Check motion detection is working (watch console logs)
   - Verify `save_interval` isn't too long
   - Check network connectivity between devices

### Debug Steps

1. **Check Nextcloud status**:
   ```bash
   curl -u username:password http://your-server:port/remote.php/webdav/
   ```

2. **Test manual upload**:
   ```bash
   curl -u username:password -T test.jpg http://your-server:port/remote.php/webdav/motion_captures/test.jpg
   ```

3. **Monitor camera logs**: Watch the console output when starting the camera system

## Security Considerations

- Use app passwords instead of main passwords when possible
- Ensure Nextcloud is properly secured (HTTPS, strong passwords)
- Consider firewall rules to restrict access
- Don't commit `nextcloud_config.py` to version control
- Regularly review uploaded images and clean up old files

## File Structure

After setup, your project should look like:
```
security_camera/
├── security_cam.py              # Main camera script
├── nextcloud_config_example.py  # Configuration template
├── nextcloud_config.py          # Your actual config (don't commit!)
└── NEXTCLOUD_SETUP.md           # This guide
```

## Performance Notes

- Images are uploaded asynchronously to avoid blocking the camera feed
- The `save_interval` setting prevents spam uploads
- Network issues won't crash the camera system
- Failed uploads are logged but don't stop motion detection

## Migration from OwnCloud

If you're migrating from OwnCloud:

1. Nextcloud uses the same WebDAV API as OwnCloud, so the integration works identically
2. Your existing OwnCloud server credentials and folders will work with Nextcloud
3. Simply update your configuration file name from `owncloud_config.py` to `nextcloud_config.py`
4. Change the dictionary name from `OWNCLOUD_CONFIG` to `NEXTCLOUD_CONFIG`
