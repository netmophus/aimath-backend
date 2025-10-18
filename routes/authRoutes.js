
const express = require("express");
const router = express.Router();
const {
  registerUser,
  loginUser,
  verifyOTP,
  getMe,
  sendResetCode,
  resetPassword,
  resendOtp,
} = require("../controllers/authController");
const authMiddleware = require("../middlewares/authMiddleware");




const User = require("../models/userModel");

// ... (tes autres routes d'auth)

// router.get("/me", authMiddleware, async (req, res) => {
//   try {
//     const u = await User.findById(req.user._id).lean();
//     if (!u) return res.status(404).json({ message: "Utilisateur introuvable." });

//     // on renvoie seulement les champs utiles (pas le hash du mot de passe)
//     const {
//       _id, phone, fullName, role, companyName, region, city,
//       commissionDefaultCfa, isActive, createdAt, updatedAt, lastLoginAt
//     } = u;

//     return res.json({
//       _id, phone, fullName, role, companyName, region, city,
//       commissionDefaultCfa, isActive, createdAt, updatedAt, lastLoginAt
//     });
//   } catch (e) {
//     console.error("/auth/me error:", e);
//     res.status(500).json({ message: "Erreur serveur." });
//   }
// });



router.post("/register", registerUser);
router.post("/login", loginUser);
router.post("/verify-otp", verifyOTP);
router.post("/resend-otp", resendOtp);  // ✅ renvoyer l'OTP
router.get("/me", authMiddleware, getMe);

// 🔁 Réinitialisation mot de passe
router.post("/send-reset-code", sendResetCode);   // ✅ envoie OTP
router.post("/reset-password", resetPassword);     // ✅ réinitialise mot de passe

module.exports = router;

