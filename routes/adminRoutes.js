const express = require("express");
const router = express.Router();
const { createAdmin, createRechargeCode } = require("../controllers/adminController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

router.post("/create", createAdmin);

// ✅ Créer un code de recharge (admin uniquement)
router.post(
  "/recharge-code",
  authMiddleware,
  authorizeRoles("admin"),
  createRechargeCode
);

module.exports = router;
