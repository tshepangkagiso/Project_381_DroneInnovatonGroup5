const express = require("express");
const router = express.Router();

//local imports
const User = require("../model/userModel");
const {authenticateToken} = require("../middleware/verification")

//routes
router.get('/dashboard', authenticateToken, async (req, res) => {
    try {
        // Assuming req.user contains the user data from the token
        const user = await User.findById(req.user.id);
        if (!user) {
            return res.status(404).send('User not found');
        }

        console.log("Reached the /dashboard route");
        res.render('DashboardsDefault', { user }); // Pass the user object to the template
    } catch (error) {
        console.error(error);
        res.status(500).send('Internal server error');
    }
});


router.post('/logout', (req, res) => {
    res.clearCookie('token'); // Clear the token cookie
    res.sendStatus(200); // Respond with success
});


//export
module.exports = router; 