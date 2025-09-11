const express = require("express");
const router = express.Router();
const { simulatePayment,  redeemCode , getAccessCodeStats, generateCodes, getAllAccessCodes, activateBatch, getCodesByBatch,activateSubscription,  nitaCallbackPublic, 
  checkNitaAndActivate,

   // 👇 AJOUTER
  assignCodesToPartner,
  getMyPartnerCodes,
  getMyPartnerStats,
  partnerMarkSold,


} = require("../controllers/paymentController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

router.all(
  '/nita/callback',
  express.urlencoded({ extended: true }),
  express.json(),
  nitaCallbackPublic
);


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
authorizeRoles("eleve", "teacher"),
  redeemCode
);







// routes/paymentRoutes.js

const logActivateReq = (req, res, next) => {
  console.log('➡️  POST /api/payments/activate-subscription');
  console.log('   userId =', req.user?._id?.toString?.());
  console.log('   auth   =', req.headers?.authorization ? 'present' : 'missing');
  console.log('   body   =', JSON.stringify(req.body));
  next();
};

router.post(
  "/activate-subscription",
  authMiddleware,
  authorizeRoles("eleve", "teacher"),
  logActivateReq,              // ✅ ajoute ce logger
  activateSubscription
);


// ✅ NOUVELLE ROUTE (check NITA côté backend + activation si payé)
router.post(
  "/nita/check-and-activate",
  authMiddleware,
  authorizeRoles("eleve", "teacher"),
  checkNitaAndActivate
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


  
  // 🔐 Admin : assigner des codes à un partenaire
router.post(
  "/assign-codes",
  authMiddleware,
  authorizeRoles("admin"),
  assignCodesToPartner
);

// 👤 Partenaire : mes stats
router.get(
  "/partners/my-stats",
  authMiddleware,
  authorizeRoles("partner"),
  getMyPartnerStats
);

// 👤 Partenaire : mes codes
router.get(
  "/partners/my-codes",
  authMiddleware,
  authorizeRoles("partner"),
  getMyPartnerCodes
);

// 👤 Partenaire : marquer un code comme vendu (enregistre la commission)
router.patch(
  "/partners/mark-sold",
  authMiddleware,
  authorizeRoles("partner"),
  partnerMarkSold
);


// routes/paymentRoutes.js (extrait)
router.get(
  "/partners/my-codes",
  authMiddleware,
  authorizeRoles("partner","admin"),
  async (req, res) => {
    try {
      const partnerId = req.user._id;
      const status = String(req.query.status || "all").toLowerCase();

      const matchStatus = status !== "all" ? { "codes.status": status } : {};
      const items = await AccessCodeBatch.aggregate([
        { $match: { "codes.partner": partnerId } },
        { $unwind: "$codes" },
        { $match: { "codes.partner": partnerId, ...matchStatus } },
        {
          $project: {
            _id: 0,
            batchId: "$batchId",
            type: "$type",
            faceValueCfa: { $ifNull: ["$codes.price", "$price"] },
            code: "$codes.code",
            status: "$codes.status",
            assignedAt: "$codes.assignedAt",
            activatedAt: "$codes.activatedAt",
            soldAt: "$codes.soldAt",
            usedAt: "$codes.usedAt",
            commissionCfa: { $ifNull: ["$codes.commissionCfa", 0] },
          }
        },
        { $sort: { assignedAt: -1, activatedAt: -1, soldAt: -1, usedAt: -1 } }
      ]);

      res.json({ count: items.length, items });
    } catch (e) {
      console.error("my-codes error:", e);
      res.status(500).json({ message: "Erreur serveur." });
    }
  }
);



module.exports = router;
