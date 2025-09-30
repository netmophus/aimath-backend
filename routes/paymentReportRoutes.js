// routes/paymentReportRoutes.js
const express = require("express");
const router = express.Router();

const { getPaymentsReport, getRecentPayments, 
    getNoSubStats,   
  listNoSubUsers, 
 } = require("../controllers/paymentReportController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// Reporting paiements (admin)
router.get(
  "/report",
  authMiddleware,
  authorizeRoles("admin"),
  getPaymentsReport
);

router.get(
  "/recent",
  authMiddleware,
  authorizeRoles("admin"),
  getRecentPayments
);


// 📊 Stats des utilisateurs sans abonnement
router.get(
  "/users/without-subscriptions/stats",
  authMiddleware,
  authorizeRoles("admin"),
  getNoSubStats
);

// 📋 Liste paginée + recherche des utilisateurs sans abonnement
router.get(
  "/users/without-subscriptions",
  authMiddleware,
  authorizeRoles("admin"),
  listNoSubUsers
);



module.exports = router;
