
# Drone Web App

This is a web application for drone management built with Node.js, Express, and MongoDB.

## Prerequisites

- Node.js
- MongoDB

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   npm install
   ```
3. Create a `.env` file in the root directory with the following variables:
   ```
   PORT=3000
   CONNECTIONSTRING=your_mongodb_connection_string
   JWT_SECRET=your_jwt_secret
   ```

## Running the Application

1. Start your MongoDB server
2. Run the application:
   ```
   npm run start , which calls nodemon app.js
   ```
3. The server should start running on the specified port (default 3000)

## Features

- User registration and login
- Password hashing for security
- JWT-based authentication
- Protected dashboard route

## Possible Challenges and Solutions

1. **Database Connection Issues**
   - Ensure MongoDB is running
   - Check the connection string in `.env`

2. **JWT Token Issues**
   - Verify JWT_SECRET is set correctly in `.env`
   - Check token expiration time (currently set to 2 minutes for login, 1 hour for registration)

3. **CORS Issues**
   - The app uses CORS middleware. If you're facing issues, check the CORS configuration in `app.js`

4. **Route Not Found**
   - Ensure all route files are correctly imported and used in `app.js`

5. **Password Hashing Errors**
   - The bcrypt library is used. Make sure it's properly installed and imported

## Security Notes

- Passwords are hashed before storing
- JWT tokens are stored in HTTP-only cookies for better security
- Sensitive routes are protected with token verification middleware

## Future Improvements

- Implement password reset functionality
- Add email verification for new registrations
- Enhance error handling and user feedback
```