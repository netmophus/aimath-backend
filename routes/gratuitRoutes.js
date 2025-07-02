const express = require("express");
const router = express.Router();
const { callGeminiGratuit } = require("../controllers/gratuitController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// 🔓 Accessible aux élèves, même inactifs
router.post("/", authMiddleware, authorizeRoles("eleve"), callGeminiGratuit);

module.exports = router;
