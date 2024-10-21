require('dotenv').config();
const jwt = require('jsonwebtoken');
const JWT_SECRET = process.env.JWT_SECRET



// Middleware to verify token
function authenticateToken(req, res, next) {
    const token = req.cookies.token; // Assuming you're using cookies
    if (!token) {
        return res.status(403).send('Forbidden');
    }

    jwt.verify(token, process.env.JWT_SECRET, (err, decoded) => {
        if (err) {
            return res.status(403).send('Forbidden');
        }
        req.user = decoded; // Set the decoded user information (e.g., id, email) on req.user
        next();
    });
}



module.exports = {authenticateToken};