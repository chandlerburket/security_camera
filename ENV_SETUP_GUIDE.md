# .env File Setup Guide

Follow these steps on your server to set up the .env file for storing login credentials.

## Step 1: Install dotenv package

Run this command in your project directory:

```bash
npm install dotenv
```

## Step 2: Create the .env file

Create a new file called `.env` in your project root directory:

```bash
nano .env
```

Or use any text editor you prefer. Add the following content:

```
CAMERA_USERNAME=your_username
CAMERA_PASSWORD=your_password
```

Replace `your_username` and `your_password` with your desired credentials.

Save and exit (in nano: Ctrl+O, Enter, Ctrl+X)

## Step 3: Set proper permissions (recommended)

Make the .env file readable only by the owner:

```bash
chmod 600 .env
```

## Step 4: Verify the setup

After making the code changes (see below), restart your server:

```bash
node server.js
```

You should see in the startup logs:

```
🔐 Login Credentials:
   - Username: your_username
   - Password: ***SET***
```

## Important Security Notes

- **Never commit the .env file to git** - it will be added to .gitignore
- The .env file should only exist on your server, not in version control
- Keep your credentials secure and change them regularly
- Use strong passwords for production environments

## Troubleshooting

If the environment variables aren't being read:
1. Make sure the `.env` file is in the project root (same directory as server.js)
2. Verify dotenv is installed: `npm list dotenv`
3. Check the server.js file has the dotenv configuration at the top
4. Restart the Node.js server completely
