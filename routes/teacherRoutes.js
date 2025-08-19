const express = require("express");
const router = express.Router();
const teacherController = require("../controllers/teacherController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const { uploadProfil, uploadToCloudinary } = require('../middlewares/uploadProfil');


// 🔐 Protéger la route pour les enseignants authentifiés
router.get("/support-requests", authMiddleware, authorizeRoles("teacher"), teacherController.getSupportRequestsForTeacher);

router.put("/support-requests/:id", authMiddleware, authorizeRoles("teacher"), teacherController.updateSupportRequestStatus);



// ✅ Marquer une session comme commencée
router.put(
  "/support-requests/:id/start-session",
  authMiddleware,
  authorizeRoles("teacher"),
  teacherController.startSessionForRequest
);





// 📸 Mettre à jour la photo de profil de l'enseignant
router.put(
  '/update-photo',
  authMiddleware,
  authorizeRoles('teacher'),
  uploadProfil,
  uploadToCloudinary,
  teacherController.updateTeacherPhoto
);


router.put(
  '/update-profile',
  authMiddleware,
  authorizeRoles('teacher'),
  teacherController.updateTeacherProfile
);




router.get(
  "/me",
  authMiddleware,
  authorizeRoles("teacher"),
  teacherController.getCurrentTeacher
);


// CRUD minimal
router.get("/",  authMiddleware, authorizeRoles("admin"), teacherController.adminListTeachers);
router.post("/",   authMiddleware,  authorizeRoles("admin"), teacherController.adminCreateTeacher);               // création sans OTP
router.patch("/:id/toggle", authorizeRoles("admin"),   authMiddleware, teacherController.adminToggleTeacherActive);
router.delete("/:id",   authMiddleware, authorizeRoles("admin"),  teacherController.adminDeleteTeacher);



module.exports = router;
