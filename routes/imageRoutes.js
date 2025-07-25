
const express = require("express");
const router = express.Router();
const multer = require("multer");

const {
  uploadAndSolveImage,
  callMathpixOCR , 
   callGptVisionSolve,
} = require("../controllers/imageToTextController");

const { callGemini ,  callGptTxtPrenuim} = require("../controllers/geminiController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

const upload = multer({ dest: "uploads/" });

// 🔵 OCR Tesseract
router.post(
  "/upload",
  authMiddleware,
  authorizeRoles("eleve"),
  upload.single("image"),
  uploadAndSolveImage
);

// 🔵 Gemini IA via texte manuel
router.post(
  "/solve",
  authMiddleware,
  authorizeRoles("eleve"),
  callGemini
);


// 🔵 GPT 4.0 Premium via texte manuel (Fahimta)
router.post(
  "/gtptxtprenuim",
  authMiddleware,
  authorizeRoles("eleve"),
  callGptTxtPrenuim
);


// 🔵 OCR Mathpix (nouvelle route)
router.post(
  "/mathpix",
  authMiddleware,
  authorizeRoles("eleve"),
  upload.single("image"),
  callMathpixOCR
);



// 🔵 GPT-Vision (analyse d'image avec OpenAI)
router.post(
  "/gpt",
  authMiddleware,
  authorizeRoles("eleve"),
  upload.single("image"),
  callGptVisionSolve
);


module.exports = router;
