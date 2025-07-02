const express = require("express");
const router = express.Router();
const { rechargeStudent } = require("../controllers/studentController");
const { createOrUpdateStudentProfile } = require("../controllers/studentProfileController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// ✅ POST /api/student/profile
router.post("/profile", authMiddleware, authorizeRoles("eleve"), createOrUpdateStudentProfile);


// // ❌ mais tu n’as pas défini cette fonction ou tu t'es trompé dans le chemin
// router.post("/recharge", authMiddleware, authorizeRoles("eleve"), rechargeStudent); // <-- undefined

router.get("/profile/me", authMiddleware, authorizeRoles("eleve"), async (req, res) => {
    try {
      const profile = await StudentProfile.findOne({ user: req.user._id });
      if (!profile) {
        return res.status(404).json({ message: "Profil non trouvé" });
      }
      res.json(profile);
    } catch (err) {
      res.status(500).json({ message: "Erreur serveur." });
    }
  });
  
module.exports = router;
