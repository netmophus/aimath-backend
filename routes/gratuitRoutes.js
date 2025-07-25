

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

} = require("../controllers/gratuitController");

const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// ✅ Appel IA (existant)
router.post("/", authMiddleware, authorizeRoles("eleve"), callGeminiGratuit);

router.post("/gtp", authMiddleware, authorizeRoles("eleve"), callGTPTextGratuit);


// ✅ LIVRES GRATUITS – élève uniquement
router.get("/:id/view", authMiddleware, authorizeRoles("eleve"), viewGratuitBook);
router.get("/:id/download", authMiddleware, authorizeRoles("eleve"), downloadGratuitBook);


// 🌍 Afficher tous les livres (public)
router.get("/", authMiddleware, authorizeRoles("eleve"), getAllBooks);

// 🌍 Afficher un seul livre par ID (optionnel)
router.get("/:id",authMiddleware, authorizeRoles("eleve"), getBookById);

// ✅ EXAMENS GRATUITS – élève uniquement
router.get("/:id/subject", authMiddleware, authorizeRoles("eleve"), getGratuitExamSubjectUrl);
router.get("/:id/correction", authMiddleware, authorizeRoles("eleve"), getGratuitExamCorrectionUrl);

// ✅ VIDEOS GRATUITS – élève uniquement
router.get("/:id/video", authMiddleware, authorizeRoles("eleve"), getGratuitVideoUrl);

module.exports = router;
