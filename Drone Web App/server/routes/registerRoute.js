const express = require("express");
const router = express.Router();
const jwt = require("jsonwebtoken")

//local imports
const User = require("../model/userModel");
const {hashPassword} = require("../Functions/bcrypt");
const JWT_SECRET = process.env.JWT_SECRET;

//routes
router.get("/register", (req, res) => {
    console.log("Reached the /register route");
    try {
        res.render('AuthenticationRegister'); 
    } catch (error) {
        res.status(400).send('Resource not found');
        console.log(error);
    }
});

router.post("/create", async (req, res) => {
    const { name, email, password } = req.body;

    try {
        const _hashedPassword = await hashPassword(password); // Use hashPassword function

        const user = new User({
            name: name,
            email: email,
            password: _hashedPassword,
        });

        await user.save();

        // Generate JWT token after successful registration
        const token = jwt.sign({ id: user._id, email: user.email }, JWT_SECRET, { expiresIn: '1h' });

        // Set token as a cookie (optional, depending on your preference)
        res.cookie('token', token, { httpOnly: true, secure: true }); // Secure if using HTTPS
        // Or send the token in the response and redirect
        res.redirect('/dashboard'); // Redirect to dashboard after registration
    } catch (error) {
        console.error("Error saving new user to database:", error);
        res.status(500).send("Error saving new user to database");
    }
});


//export
module.exports = router; 