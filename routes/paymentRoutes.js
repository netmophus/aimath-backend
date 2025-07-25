const express = require("express");
const router = express.Router();
const { simulatePayment,  redeemCode , getAccessCodeStats, generateCodes, getAllAccessCodes, activateBatch, getCodesByBatch} = require("../controllers/paymentController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// 📌 Route protégée : seul un élève connecté peut appeler /simulate
router.post(
  "/simulate",
  authMiddleware,
  authorizeRoles("eleve"),
  simulatePayment
);

// ✅ Validation d'un code d'accès
router.post(
  "/redeem-code",
  authMiddleware,
  authorizeRoles("eleve"),
  redeemCode
);


// 📌 Génération de codes d'accès — réservé aux admins
router.post(
  "/generate-codes",
  authMiddleware,
  authorizeRoles("admin"),
  generateCodes
);


router.get(
  "/codes",
  authMiddleware,
  authorizeRoles("admin"),
  getAllAccessCodes
);

router.get(
  "/codes/by-batch/:batchId",
  authMiddleware,
  authorizeRoles("admin"),
  getCodesByBatch
);


router.post(
  "/activate-batch",
  authMiddleware,
  authorizeRoles("admin"),
  activateBatch
);

router.get("/stats", 
   authMiddleware,
  authorizeRoles("admin"),  
  getAccessCodeStats);


module.exports = router;
