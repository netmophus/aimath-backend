// const express = require("express");
// const router = express.Router();
// const multer = require("multer");
// const { uploadAndSolveImage,  solveExercise } = require("../controllers/imageToTextController");
// const authMiddleware = require("../middlewares/authMiddleware");
// const { authorizeRoles } = require("../middlewares/roleMiddleware");

// const upload = multer({ dest: "uploads/" }); // dossier temporaire

// router.post(
//   "/upload",
//   authMiddleware,
//   authorizeRoles("eleve"),
//   upload.single("image"),
//   uploadAndSolveImage
// );


// // ✍️ Route pour saisie de question manuelle
// router.post(
//     "/solve",
//     authMiddleware,
//     authorizeRoles("eleve"),
//     iaUsageLimiter,
//     solveExercise
//   );

// module.exports = router;



const express = require("express");
const router = express.Router();
const multer = require("multer");

const { uploadAndSolveImage } = require("../controllers/imageToTextController");
const { callGemini } = require("../controllers/geminiController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const iaUsageLimiter = require("../middlewares/iaUsageLimiter"); // ✅ À ajouter

const upload = multer({ dest: "uploads/" });

// Image route
router.post(
  "/upload",
  authMiddleware,
  authorizeRoles("eleve"),
  upload.single("image"),
  // iaUsageLimiter, // 👈 AJOUT ICI pour bloquer après 10 requêtes
  uploadAndSolveImage
);

// Texte manuel
router.post(
  "/solve",
  authMiddleware,
  authorizeRoles("eleve"),
  // iaUsageLimiter,
  callGemini
);

module.exports = router;
