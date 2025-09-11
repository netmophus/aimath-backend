const express = require("express");
const router = express.Router();
const premiumController = require("../controllers/premiumController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");



// 🌍 Afficher tous les livres (public)
router.get("/", authMiddleware, authorizeRoles("eleve", "teacher"), premiumController.getAllBooks);

// 🌍 Afficher un seul livre par ID (optionnel)
router.get("/:id",authMiddleware, authorizeRoles("eleve", "teacher"), premiumController.getBookById);


// 🔐 Télécharger un livre (réservé aux élèves)
router.get(
  "/books/:id/download",
  authMiddleware,
  authorizeRoles("eleve", "teacher"),
  premiumController.downloadBookWithLimit
);

// 🔐 Visualiser un livre (réservé aux élèves)
router.get(
  "/books/:id/view",
  authMiddleware,
  authorizeRoles("eleve", "teacher"),
  premiumController.viewBook
);


router.get(
  "/exams/:id/download-subject",
  authMiddleware,
  authorizeRoles("eleve", "teacher"),
  premiumController.downloadExamWithLimit
);

router.get(
  "/exams/:id/download-correction",
  authMiddleware,
  authorizeRoles("eleve", "teacher"),
  premiumController.downloadCorrectionWithLimit
);





module.exports = router;
