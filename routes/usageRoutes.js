const express = require("express");
const router = express.Router();
const usageController = require("../controllers/usageController");
const authMiddleware = require("../middlewares/authMiddleware");

router.get("/me", authMiddleware, usageController.getMyMonthlyUsage);

module.exports = router;
