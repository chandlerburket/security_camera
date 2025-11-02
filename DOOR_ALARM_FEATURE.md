# Door Alarm Feature

A door alarm system has been added to the security camera server that plays an audio file when the door is opened while the alarm is active.

## Features

- Toggle button in the web interface to enable/disable the door alarm
- Visual indicator showing when alarm is active
- Plays audio file on the server when door opens while alarm is enabled
- **Pushover notifications sent to your phone when alarm is triggered**
- Real-time synchronization across all connected clients via Socket.io
- Flashing visual alarm when triggered

## How It Works

1. **Enable Alarm**: Click the "Enable Door Alarm" button in the web interface
2. **Armed State**: The alarm is now active and monitoring door status
3. **Detection**: When the door transitions from "closed" to "open" while alarm is active:
   - Server plays an audio file locally
   - Pushover notification is sent to your phone (if configured)
   - All connected web clients receive an alarm event
   - Visual alarm status flashes red
   - Console logs the alarm event

## Server-Side Implementation

### New Endpoints

- `POST /toggle-alarm` - Toggle the door alarm on/off
  - Returns: `{ status: 'success', alarm_enabled: boolean, message: string }`

### Key Functions (server.js)

- `playAlarmSound()` (line 219-242) - Plays audio file when alarm triggers
- `checkDoorAlarm(newDoorState)` (line 245-264) - Monitors door state changes
- Door alarm is checked in `/webhook` endpoint (line 474)

### Audio Playback

The server attempts to play an audio file using system audio players:
- Linux: `aplay` (ALSA) or `mpg123`
- macOS: `afplay`
- Cross-platform: `ffplay` (ffmpeg)

### Configuration

Set the alarm sound file path via environment variable:
```bash
export ALARM_SOUND_FILE="/path/to/your/alarm.mp3"
```

Default: `./alarm.mp3` in the project root

### Pushover Notifications

The door alarm can send push notifications to your phone via Pushover when triggered.

**Configuration:**

1. Configure Pushover in `server_integrations_config.local.js`:
   ```javascript
   pushover: {
       enabled: true,
       apiToken: 'YOUR_PUSHOVER_API_TOKEN',
       userKey: 'YOUR_PUSHOVER_USER_KEY',
       notifyInterval: 60,  // Minimum seconds between notifications
       priority: 1,         // Priority level (1 = high priority for alarms)
       sound: 'siren'       // Notification sound (siren for alarms)
   }
   ```

2. Get Pushover credentials:
   - Sign up at https://pushover.net/
   - Create an application to get your API token
   - Find your user key in your account settings

**Features:**
- Sends notification with alarm details and timestamp
- Uses high priority and siren sound by default
- Respects notification interval to prevent spam
- Separate tracking from motion detection notifications

**Notification Message:**
```
🚨 DOOR ALARM TRIGGERED!

The door was opened while the alarm was active.

Time: [timestamp]
```

## Web Interface

### UI Components

1. **Toggle Button** (index.html:228)
   - Gray when disabled
   - Red when active
   - Located next to recording button

2. **Status Indicator** (index.html:209-211)
   - Shows "🚨 Door Alarm Active" when enabled
   - Hidden when disabled
   - Flashes when alarm is triggered

### Client-Side Functions

- `toggleAlarm()` - Sends toggle request to server
- `updateAlarmUI(isEnabled)` - Updates button and status display
- Socket.io listeners for real-time updates:
  - `alarm-status` - Syncs alarm state across clients
  - `door-alarm` - Receives alarm trigger events

## Installation Requirements

### Audio Player (Linux)

Install an audio player on your server:

```bash
# Option 1: ALSA utilities (for WAV files)
sudo apt-get install alsa-utils

# Option 2: mpg123 (for MP3 files)
sudo apt-get install mpg123

# Option 3: ffmpeg (supports all formats)
sudo apt-get install ffmpeg
```

### Audio File

Place an alarm sound file in the project directory:

```bash
# Example: Download a free alarm sound
wget -O alarm.mp3 "https://example.com/alarm.mp3"

# Or use a system sound
cp /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga alarm.mp3
```

Supported formats: MP3, WAV, OGG, etc. (depends on installed player)

## Usage

1. **Start the server**:
   ```bash
   node server.js
   ```

2. **Open web interface**:
   ```
   http://localhost:5000
   ```

3. **Enable alarm**:
   - Click "Enable Door Alarm" button
   - Status shows "🚨 Door Alarm Active"

4. **Test the alarm**:
   - Trigger your door sensor to change from "closed" to "open"
   - Server will play the alarm sound
   - Web interface will flash the alarm status

5. **Disable alarm**:
   - Click "Disable Door Alarm" button

## State Persistence

- Alarm state is stored in server memory (`doorAlarmEnabled` variable)
- State is broadcast to all connected clients via Socket.io
- State resets when server restarts (not persisted to disk)

## Technical Details

### Server Variables (server.js)

```javascript
let doorAlarmEnabled = false;    // Current alarm state
let lastDoorState = null;        // Previous door state for comparison
```

### Socket.io Events

**Outgoing (Server → Clients)**:
- `alarm-status` - Broadcast when alarm is toggled
  ```javascript
  { enabled: boolean, timestamp: number }
  ```
- `door-alarm` - Broadcast when alarm is triggered
  ```javascript
  { timestamp: number, message: string }
  ```

**Status Endpoint Response**:
The `/status` endpoint now includes:
```javascript
{
  ...
  alarm_enabled: boolean,
  ...
}
```

## Styling

Button colors:
- Disabled: Gray (#6c757d)
- Active: Red (#dc3545)
- Hover: Darker shades

Alarm status:
- Background: Transparent red
- Border: Solid red
- Flash animation: 1 second, 3 iterations

## Future Enhancements

Potential improvements:
- Persist alarm state to database/file
- Add alarm scheduling (enable/disable at specific times)
- Multiple alarm sounds based on time of day
- Email/SMS notifications when alarm triggers
- Alarm history/log
- Configurable alarm sensitivity
- Snooze functionality
- Attach camera snapshot to Pushover notification

## Troubleshooting

### Alarm not playing sound

1. Check if audio file exists:
   ```bash
   ls -la alarm.mp3
   ```

2. Check audio player is installed:
   ```bash
   which aplay mpg123 ffplay
   ```

3. Test audio manually:
   ```bash
   aplay alarm.mp3
   # or
   mpg123 alarm.mp3
   ```

4. Check server console for error messages

5. Verify server has audio output configured

### Button not changing state

1. Check browser console for JavaScript errors
2. Verify server is running
3. Check network tab for failed requests
4. Ensure Socket.io is connected

### Alarm triggering unexpectedly

1. Check door sensor is sending correct state values ("open"/"closed")
2. Verify `lastDoorState` is being tracked correctly
3. Check server logs for door state transitions

### Pushover notifications not working

1. Verify Pushover is enabled in config:
   ```javascript
   pushover: { enabled: true, ... }
   ```

2. Check API credentials are correct:
   - API Token from your Pushover application
   - User Key from your Pushover account

3. Check server logs for Pushover errors:
   ```
   🔔 Door alarm Pushover notification sent  (success)
   ❌ Door alarm Pushover error: ...  (failure)
   ```

4. Verify notification interval hasn't blocked the notification:
   ```
   ⏭️  Skipping door alarm notification (too soon after last one)
   ```

5. Test Pushover manually:
   ```bash
   curl -s \
     --form-string "token=YOUR_API_TOKEN" \
     --form-string "user=YOUR_USER_KEY" \
     --form-string "message=Test message" \
     https://api.pushover.net/1/messages.json
   ```
