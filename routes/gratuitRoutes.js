

const express = require("express");
const router = express.Router();

const {
  callGeminiGratuit,
  callGTPTextGratuit,
  viewGratuitBook,
  downloadGratuitBook,
  getGratuitExamSubjectUrl,
  getGratuitExamCorrectionUrl,
 getGratuitVideoUrl,
 getAllBooks,
 getBookById,
 getBooksByLevels,

} = require("../controllers/gratuitController");

const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// ✅ Appel IA (existant)
router.post("/", authMiddleware, authorizeRoles("eleve", "teacher"), callGeminiGratuit);

router.post("/gtp", authMiddleware, authorizeRoles("eleve", "teacher"), callGTPTextGratuit);

// 📚 Livres par plusieurs levels: /ia/gratuit/levels?in=6eme,5eme,terminale
router.get(
  "/levels",
  authMiddleware,
  authorizeRoles("eleve", "teacher"),
  getBooksByLevels
);

// ✅ LIVRES GRATUITS – élève uniquement
router.get("/:id/view", authMiddleware, authorizeRoles("eleve", "teacher"), viewGratuitBook);
router.get("/:id/download", authMiddleware, authorizeRoles("eleve", "teacher"), downloadGratuitBook);


// 🌍 Afficher tous les livres (public)
router.get("/", authMiddleware, authorizeRoles("eleve", "teacher"), getAllBooks);

// 🌍 Afficher un seul livre par ID (optionnel)
router.get("/:id",authMiddleware, authorizeRoles("eleve", "teacher"), getBookById);

// ✅ EXAMENS GRATUITS – élève uniquement
router.get("/:id/subject", authMiddleware, authorizeRoles("eleve", "teacher"), getGratuitExamSubjectUrl);
router.get("/:id/correction", authMiddleware, authorizeRoles("eleve", "teacher"), getGratuitExamCorrectionUrl);

// ✅ VIDEOS GRATUITS – élève uniquement
router.get("/:id/video", authMiddleware, authorizeRoles("eleve", "teacher"), getGratuitVideoUrl);

module.exports = router;
