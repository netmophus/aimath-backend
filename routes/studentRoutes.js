const express = require("express");
const router = express.Router();

const { createOrUpdateStudentProfile } = require("../controllers/studentController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const StudentProfile = require("../models/studentProfileModel");

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




  
module.exports = router;
