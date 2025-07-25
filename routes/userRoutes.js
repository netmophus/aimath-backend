const express = require("express");
const router = express.Router();

const Teacher = require("../models/Teacher"); // 👈 à importer en haut
const {
  createTeacher,
  getAllTeachers,
  updateTeacher,
  deleteTeacher,
  toggleTeacherStatus,
} = require("../controllers/userController");
// const authMiddleware = require("../middlewares/authMiddleware");
// const { authorizeRoles } = require("../middlewares/roleMiddleware");

const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");


// Toutes ces routes sont réservées à l’admin
router.post("/teachers", authMiddleware, authorizeRoles("admin"), createTeacher);
router.get("/teachers", authMiddleware, authorizeRoles("admin"), getAllTeachers);
router.put("/teachers/:id", authMiddleware, authorizeRoles("admin"), updateTeacher);
router.delete("/teachers/:id", authMiddleware, authorizeRoles("admin"), deleteTeacher);
router.patch("/teachers/:id/toggle", authMiddleware, authorizeRoles("admin"), toggleTeacherStatus);


// // 👇 Route pour récupérer le profil de l'utilisateur connecté (enseignant)
// router.get(
//   "/profile",
//   authMiddleware,
//   authorizeRoles("teacher"),
//   (req, res) => {
//     res.json(req.user); // Renvoie le profil sans mot de passe
//   }
// );







// ✅ Mettre à jour le profil TEACHER (pas User)

router.put("/profile", authMiddleware, authorizeRoles("teacher"), async (req, res) => {
  try {
    const user = req.user;

    const fieldsToUpdate = ["fullName", "schoolName", "city", "phone", "email"];
    fieldsToUpdate.forEach((field) => {
      if (req.body[field]) {
        user[field] = req.body[field];
      }
    });


    if (req.body.photo) {
  user.photo = req.body.photo;
}


    // Marquer comme complété si les infos clés sont présentes
    if (
      user.fullName &&
      user.schoolName &&
      user.city &&
      req.body.subjects?.length &&
      req.body.levels?.length
    ) {
      user.profileCompleted = true;
    }

    // Enregistre les infos de base de l’utilisateur
    await user.save();

    // Enregistre ou met à jour le modèle Teacher séparé
    const Teacher = require("../models/Teacher");
    const existingProfile = await Teacher.findOne({ userId: user._id });

   if (existingProfile) {
  existingProfile.subjects = req.body.subjects || existingProfile.subjects;
  existingProfile.levels = req.body.levels || existingProfile.levels;
  existingProfile.level = req.body.level || existingProfile.level;
  existingProfile.gpsLocation = req.body.gpsLocation || existingProfile.gpsLocation;
  existingProfile.experience = req.body.experience || existingProfile.experience;
  await existingProfile.save();
} else {
  await Teacher.create({
    userId: user._id,
    subjects: req.body.subjects,
    levels: req.body.levels,
    level: req.body.level,
    gpsLocation: req.body.gpsLocation,
    experience: req.body.experience,
  });
}


    res.json({ message: "Profil mis à jour avec succès." });
  } catch (err) {
    console.error("Erreur update profile:", err);
    res.status(500).json({ message: "Erreur serveur lors de la mise à jour du profil." });
  }
});




router.get(
  "/profile",
  authMiddleware,
  authorizeRoles("teacher"),
  async (req, res) => {
    try {
      const user = req.user;
      const teacherData = await Teacher.findOne({ userId: user._id });

      const userInfo = {
        _id: user._id,
        fullName: user.fullName,
        schoolName: user.schoolName,
        city: user.city,
        phone: user.phone,
        email: user.email,
        photo: user.photo,
        profileCompleted: user.profileCompleted,
      };

      const teacherInfo = teacherData
        ? {
            subjects: teacherData.subjects,
            levels: teacherData.levels,
            experience: teacherData.experience,
            level: teacherData.level,           
            gpsLocation: teacherData.gpsLocation,
          }
        : {
            subjects: [],
            levels: [],
            experience: "",
            level: "",            
            gpsLocation: "",
          };

      res.json({ ...userInfo, ...teacherInfo });
    } catch (err) {
      console.error("Erreur chargement profil:", err);
      res.status(500).json({ message: "Erreur serveur." });
    }
  }
);



module.exports = router;
