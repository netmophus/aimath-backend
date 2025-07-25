// const express = require("express");
// const router = express.Router();
// const { registerUser, loginUser } = require("../controllers/authController");
// const { verifyOTP } = require("../controllers/authController");
// const { getMe } = require("../controllers/authController");
// const authMiddleware = require("../middlewares/authMiddleware");

// // ✅ POST /api/auth/register
// router.post("/register", registerUser);

// // ✅ POST /api/auth/login
// router.post("/login", loginUser);


// router.post("/verify-otp", verifyOTP);

// router.get("/me", authMiddleware, getMe);

// module.exports = router;




const express = require("express");
const router = express.Router();
const {
  registerUser,
  loginUser,
  verifyOTP,
  getMe,
  sendResetCode,     // ✅ à ajouter
  resetPassword,     // ✅ à ajouter
} = require("../controllers/authController");
const authMiddleware = require("../middlewares/authMiddleware");

router.post("/register", registerUser);
router.post("/login", loginUser);
router.post("/verify-otp", verifyOTP);
router.get("/me", authMiddleware, getMe);

// 🔁 Réinitialisation mot de passe
router.post("/send-reset-code", sendResetCode);   // ✅ envoie OTP
router.post("/reset-password", resetPassword);     // ✅ réinitialise mot de passe

module.exports = router;

