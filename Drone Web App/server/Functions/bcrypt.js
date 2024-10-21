const bcrypt = require("bcrypt");

async function hashPassword(plainPassword) {
    try {
        const saltRounds = 10;
        const salt = await bcrypt.genSalt(saltRounds);
        const hashedPassword = await bcrypt.hash(plainPassword, salt);
        console.log("Hashed Password: ", hashedPassword);
        return hashedPassword;
    } catch (error) {
        console.error("Error hashing password: ", error);
        throw error;
    }
}

async function verifyPassword(plainPassword, hashedPassword) {
    try {
        const match = await bcrypt.compare(plainPassword, hashedPassword);

        if (match) {
            console.log("Password is correct!");
            return true;
        } else {
            console.log("Password is incorrect.");
            return false;
        }
    } catch (error) {
        console.error("Error verifying password: ", error);
        throw error;
    }
}



module.exports = {hashPassword, verifyPassword};

