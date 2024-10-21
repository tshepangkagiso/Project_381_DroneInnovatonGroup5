require("dotenv").config();
const express = require("express");
const router = express.Router();
const jwt = require("jsonwebtoken")

//local imports
const User = require("../model/userModel");
const {verifyPassword} = require("../Functions/bcrypt");
const JWT_SECRET = process.env.JWT_SECRET;

//routes
router.get("/login", (req, res) => {
    try {
        res.render('AuthenticationLogin'); 
    } catch (error) {
        res.status(400).send('Resource not found');
        console.log(error);
    }
});

router.post("/login", async (req, res) => {
    const { email, password } = req.body;

    if (!email || !password) {
        return res.status(400).send("Email and password are required.");
    }

    try {
        const user = await User.findOne({ email: email });
        if (user) {
            const correctPassword = await verifyPassword(password, user.password);
            if (correctPassword) {
                const token = jwt.sign({ id: user._id, email: user.email }, JWT_SECRET, { expiresIn: '2m' });

                // Set the token in an HTTP-only cookie
                res.cookie('token', token, { httpOnly: true, secure: process.env.NODE_ENV === 'production' });
                
                // Redirect to the dashboard after login
                res.redirect("http://localhost:3000/dashboard"); 
            } else {
                return res.sendStatus(401); // Unauthorized
            }
        } else {
            return res.sendStatus(404); // User not found
        }
    } catch (error) {
        console.error('Error during login:', error);
        return res.status(500).send('Internal server error');
    }
}); 

router.post('/logout', (req, res) => {
    res.clearCookie('token'); // Clear the JWT cookie
    res.status(200).send('Logged out successfully');
});



//export
module.exports = router; 

