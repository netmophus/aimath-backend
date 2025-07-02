const express = require("express");
const router = express.Router();
const { registerUser, loginUser } = require("../controllers/authController");
const { verifyOTP } = require("../controllers/authController");
const { getMe } = require("../controllers/authController");
const authMiddleware = require("../middlewares/authMiddleware");

// ✅ POST /api/auth/register
router.post("/register", registerUser);

// ✅ POST /api/auth/login
router.post("/login", loginUser);


router.post("/verify-otp", verifyOTP);

router.get("/me", authMiddleware, getMe);

module.exports = router;
