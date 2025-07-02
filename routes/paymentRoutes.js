const express = require("express");
const router = express.Router();
const { simulatePayment } = require("../controllers/paymentController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// 📌 Route protégée : seul un élève connecté peut appeler /simulate
router.post(
  "/simulate",
  authMiddleware,
  authorizeRoles("eleve"),
  simulatePayment
);

module.exports = router;
