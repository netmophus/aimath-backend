const express = require("express");
const router = express.Router();

const { createOrUpdateStudentProfile } = require("../controllers/studentController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const StudentProfile = require("../models/studentProfileModel");
const MonthlyUsage = require("../models/MonthlyUsage");


const { uploadProfil, uploadToCloudinary } = require('../middlewares/uploadProfil');

// POST /api/student/profile (avec photo upload)
router.post(
  '/profile',
  authMiddleware,
  authorizeRoles('eleve'),
  uploadProfil,
  uploadToCloudinary,
  createOrUpdateStudentProfile
);


router.get(
  '/profile',
  authMiddleware,
  authorizeRoles('eleve'),
  async (req, res) => {
    try {
      const user = req.user;

      console.log('🔍 Utilisateur connecté (eleve) :', user);

      if (!user) {
        return res.status(401).json({ message: "Utilisateur non autorisé." });
      }

      const studentData = await StudentProfile.findOne({ user: user._id });

      if (!studentData) {
        console.warn('⚠️ Aucun profil élève trouvé pour cet utilisateur.');
      }

      res.json({
        fullName: user.fullName,
        phone: user.phone,
        schoolName: user.schoolName,
        city: user.city,
        photo: user.photo,
        level: studentData?.level || '',
        classe: studentData?.classe || '',

          // ✅ Ajoute ces deux lignes :
  isSubscribed: user.isSubscribed,
  subscriptionEnd: user.subscriptionEnd,
      });
    } catch (err) {
      console.error("❌ Erreur chargement profil élève :", err.message, err.stack);

      res.status(500).json({ message: "Erreur serveur." });
    }
  }
);


// routes/studentRoutes.js
// routes/studentRoutes.js
const REQUESTS_PER_MONTH = Number(process.env.REQUESTS_PER_MONTH || 2);

router.get("/me/requests-usage", authMiddleware, async (req, res) => {
  try {
    const period = new Date().toISOString().slice(0,7);
    const usage = await MonthlyUsage.findOne({ user: req.user._id, period })
      .select("supportRequestsCreated");
    const used = usage?.supportRequestsCreated || 0;
    const limit = REQUESTS_PER_MONTH;
    return res.json({ period, used, limit, remaining: Math.max(0, limit - used) });
  } catch (e) {
    console.error("me/requests-usage error", e);
    return res.status(500).json({ message: "Erreur serveur." });
  }
});



  
module.exports = router;
