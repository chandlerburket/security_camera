# Nextcloud and Pushover Migration Summary

The Nextcloud and Pushover features have been successfully migrated from the camera client to the server.

## What Changed

### Server Side (server.js)
- Added Nextcloud upload functionality (WebDAV)
- Added Pushover notification functionality
- Created new API endpoints:
  - `POST /api/camera/motion-image` - Receives motion detection images from camera
  - `POST /api/camera/video` - Receives video recordings from camera
- Server now handles all Nextcloud uploads and Pushover notifications

### Camera Client (camera_client.py)
- Removed direct Nextcloud and Pushover integration code
- Removed `configure_nextcloud()` and `configure_pushover()` methods
- Replaced local handling with server API calls:
  - `upload_motion_image_to_server()` - Sends motion images to server
  - `_upload_video_to_server()` - Sends video recordings to server
- No longer needs nextcloud_config.py or pushover_config.py

## Setup Instructions

### 1. Install Required NPM Packages

Run the following command in the project directory:

```bash
npm install axios form-data
```


### 2. Configure Server Integrations

1. Copy the configuration template:
   ```bash
   cp server_integrations_config.js server_integrations_config.local.js
   ```

2. Edit `server_integrations_config.local.js` with your credentials:
   ```javascript
   module.exports = {
       nextcloud: {
           enabled: true,
           url: "http://your-nextcloud-server",
           username: "your_username",
           password: "your_password",
           motionFolder: "/motion_captures",
           videoFolder: "/recordings",
           saveInterval: 10
       },
       pushover: {
           enabled: true,
           userKey: "your_user_key",
           apiToken: "your_api_token",
           notifyInterval: 120,
           priority: 0,
           sound: "pushover"
       }
   };
   ```

3. Restart the server

### 3. Camera Client No Longer Needs Local Config

The camera client no longer needs:
- `nextcloud_config.py`
- `pushover_config.py`

All configuration is now done on the server side.

## Benefits of This Migration

1. **Centralized Configuration**: All integration settings are managed in one place (the server)
2. **Reduced Client Load**: Camera clients are lighter and don't need to handle uploads/notifications
3. **Better Scalability**: Multiple cameras can use the same Nextcloud/Pushover configuration
4. **Easier Updates**: Change integration settings without touching camera clients
5. **Network Efficiency**: Server can batch operations and handle retries more efficiently
6. **Security**: Credentials are stored only on the server, not on each camera device

## How It Works

1. Camera client detects motion and sends image to server via `/api/camera/motion-image`
2. Server checks save interval and decides whether to process the image
3. If enabled, server sends Pushover notification with image attachment
4. If enabled, server uploads image to Nextcloud via WebDAV
5. Same process for video recordings via `/api/camera/video`

## Files Modified

- `server.js` - Added integrations and new endpoints
- `camera_client.py` - Removed direct integrations, added server upload methods
- `server_integrations_config.js` - New configuration template

## Files Created

- `npm-packages-needed.txt` - List of required npm packages
- `server_integrations_config.js` - Configuration template
- `MIGRATION_SUMMARY.md` - This file
