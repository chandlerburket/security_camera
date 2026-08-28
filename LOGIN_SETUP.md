# Login Page Setup

A basic login page has been created for the security camera web interface.

## Accessing the Login Page

The login page is available at:
```
http://[server-ip]:5000/login
```

## Default Credentials

By default, the login credentials are:
- **Username**: `admin`
- **Password**: `admin`

## Changing Login Credentials

You can change the login credentials using environment variables:

### Option 1: Environment Variables (Recommended)

```bash
export CAMERA_USERNAME="your_username"
export CAMERA_PASSWORD="your_password"
node server.js
```

### Option 2: Using a .env file

1. Install the `dotenv` package:
   ```bash
   npm install dotenv
   ```

2. Create a `.env` file in the project root:
   ```
   CAMERA_USERNAME=your_username
   CAMERA_PASSWORD=your_password
   ```

3. Add this line at the top of `server.js` (after the requires):
   ```javascript
   require('dotenv').config();
   ```

4. Start the server:
   ```bash
   node server.js
   ```

## Features

- Clean, modern interface matching the main page styling
- "Remember me" checkbox to persist login
- Client-side validation
- Loading states during authentication
- Error message display
- Session/localStorage token storage
- Responsive design for mobile devices

## Security Notes

⚠️ **IMPORTANT**: This is a basic authentication implementation for demonstration purposes.

For production use, you should implement:

1. **Password Hashing**: Use bcrypt or similar to hash passwords
   ```bash
   npm install bcrypt
   ```

2. **JWT Tokens**: Use proper JWT authentication
   ```bash
   npm install jsonwebtoken
   ```

3. **HTTPS**: Always use HTTPS in production to encrypt credentials in transit

4. **Rate Limiting**: Implement rate limiting to prevent brute force attacks
   ```bash
   npm install express-rate-limit
   ```

5. **Secure Session Management**: Use express-session with secure cookies

6. **Authentication Middleware**: Protect routes with authentication middleware

## Current Implementation

The login endpoint at `/api/login` (server.js:467-498):
- Accepts POST requests with username, password, and remember flag
- Compares credentials with environment variables
- Returns a basic token on success
- Stores token in sessionStorage (default) or localStorage (if "remember me" is checked)

## Next Steps for Production

1. Implement proper password hashing
2. Use JWT for token generation
3. Add middleware to protect routes
4. Implement token expiration and refresh
5. Add logout functionality
6. Set up HTTPS
7. Add rate limiting
8. Consider using a proper authentication library like Passport.js
