const express = require("express");
const router = express.Router();
const { callGemini } = require("../controllers/geminiController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// 🧠 Accès élève uniquement
router.post("/solve", authMiddleware, authorizeRoles("eleve"), callGemini);

module.exports = router;
