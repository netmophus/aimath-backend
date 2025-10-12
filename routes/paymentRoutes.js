const express = require("express");
const router = express.Router();
const { simulatePayment,  redeemCode , getAccessCodeStats, generateCodes, getAllAccessCodes, activateBatch, getCodesByBatch,activateSubscription,  nitaCallbackPublic, 
  checkNitaAndActivate,

   // 👇 AJOUTER
  assignCodesToPartner,
  getMyPartnerCodes,
  getMyPartnerStats,
  partnerMarkSold,
nitaCreateAchatServer,

} = require("../controllers/paymentController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

router.all(
  '/nita/callback',
  express.urlencoded({ extended: true }),
  express.json(),
  nitaCallbackPublic
);


// + ajouter la route protégée
router.post(
  "/nita/create",
  authMiddleware,
  authorizeRoles("eleve","teacher"),
  nitaCreateAchatServer
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

// 👤 Partenaire : vendre une carte à un élève
router.post(
  "/partners/sell-card",
  authMiddleware,
  authorizeRoles("partner", "admin"),
  async (req, res) => {
    try {
      const { cardId, studentId, studentName, studentPhone, paymentMethod, notes, saleAmount } = req.body;
      const partnerId = req.user._id;
      
      // 1. Récupérer le code et le marquer comme vendu
      const AccessCodeBatch = require("../models/AccessCodeBatch");
      const mongoose = require("mongoose");
      
      // Essayer de trouver par _id d'abord
      let batch = await AccessCodeBatch.findOne({ "codes._id": mongoose.Types.ObjectId.isValid(cardId) ? cardId : null });
      let codeIndex = -1;
      
      if (batch) {
        codeIndex = batch.codes.findIndex(c => c._id.toString() === cardId);
      }
      
      // Si pas trouvé, chercher par code string
      if (!batch || codeIndex === -1) {
        const allBatches = await AccessCodeBatch.find({ "codes.partner": partnerId });
        
        for (const b of allBatches) {
          const idx = b.codes.findIndex(c => 
            (c._id && c._id.toString() === cardId) || 
            (c.code && c.code === cardId)
          );
          if (idx !== -1) {
            batch = b;
            codeIndex = idx;
            break;
          }
        }
      }
      
      if (!batch || codeIndex === -1) {
        return res.status(404).json({ message: "Carte non trouvée" });
      }
      
      const code = batch.codes[codeIndex];
      
      // Vérifier que le code appartient au partenaire
      if (code.partner.toString() !== partnerId.toString()) {
        return res.status(403).json({ message: "Ce code ne vous appartient pas" });
      }
      
      // Vérifier que le code n'est pas déjà vendu
      if (code.status === "sold" || code.status === "used") {
        return res.status(400).json({ message: "Ce code a déjà été vendu ou utilisé" });
      }
      
      // Récupérer les informations du partenaire pour la commission
      const User = require("../models/userModel");
      const partner = await User.findById(partnerId);
      
      // Calculer la commission (utiliser commissionDefaultCfa du partenaire)
      const commissionAmount = Number(partner?.commissionDefaultCfa || 0);
      console.log(`💰 Commission calculée: ${commissionAmount} FCFA pour partenaire ${partner?.fullName}`);
      
      // Marquer comme vendu avec commission
      batch.codes[codeIndex].status = "sold";
      batch.codes[codeIndex].soldAt = new Date();
      batch.codes[codeIndex].studentId = studentId;
      batch.codes[codeIndex].studentName = studentName;
      batch.codes[codeIndex].studentPhone = studentPhone;
      batch.codes[codeIndex].commissionCfa = commissionAmount; // ✅ Enregistrer la commission
      
      await batch.save();
      
      // 2. Créer un enregistrement de vente
      const saleId = `SALE-${Date.now()}-${code.code.slice(-6)}`;
      
      res.json({ 
        message: "Carte vendue avec succès",
        saleId: saleId,
        code: code.code
      });
    } catch (error) {
      console.error("Erreur vente carte:", error);
      res.status(500).json({ message: "Erreur serveur lors de la vente", error: error.message });
    }
  }
);

// 👤 Partenaire : envoyer SMS à un élève (après vente)
router.post(
  "/partners/send-sms-to-student",
  authMiddleware,
  authorizeRoles("partner", "admin"),
  async (req, res) => {
    try {
      const { studentId, message } = req.body;

      if (!message || message.trim() === "") {
        return res.status(400).json({ message: "Le message ne peut pas être vide." });
      }

      const User = require("../models/userModel");
      const student = await User.findById(studentId);
      
      if (!student) {
        return res.status(404).json({ message: "Élève non trouvé." });
      }

      if (!student.phone) {
        return res.status(400).json({ message: "Cet élève n'a pas de numéro de téléphone." });
      }

      const { sendSMS } = require("../utils/sendSMS");
      const result = await sendSMS(student.phone, message);

      if (result.success) {
        res.json({ message: "SMS envoyé avec succès à l'élève" });
      } else {
        res.status(500).json({ message: "Échec de l'envoi du SMS" });
      }
    } catch (error) {
      console.error("Erreur envoi SMS élève:", error);
      res.status(500).json({ message: "Erreur serveur lors de l'envoi du SMS" });
    }
  }
);

// 👤 Partenaire : recalculer les commissions des ventes passées
router.post(
  "/partners/recalculate-commissions",
  authMiddleware,
  authorizeRoles("partner", "admin"),
  async (req, res) => {
    try {
      const partnerId = req.user._id;
      
      // Récupérer le partenaire pour connaître sa commission
      const User = require("../models/userModel");
      const partner = await User.findById(partnerId);
      
      if (!partner || !partner.commissionDefaultCfa) {
        return res.status(400).json({ message: "Commission non configurée pour ce partenaire" });
      }
      
      const AccessCodeBatch = require("../models/AccessCodeBatch");
      const commissionAmount = partner.commissionDefaultCfa;
      
      // Trouver tous les codes vendus par ce partenaire sans commission
      const batches = await AccessCodeBatch.find({ "codes.partner": partnerId });
      
      let updatedCount = 0;
      let totalCommission = 0;
      
      for (const batch of batches) {
        let batchModified = false;
        
        for (let i = 0; i < batch.codes.length; i++) {
          const code = batch.codes[i];
          
          // Si le code appartient au partenaire, est vendu, mais n'a pas de commission
          if (code.partner.toString() === partnerId.toString() && 
              code.status === "sold" && 
              (!code.commissionCfa || code.commissionCfa === 0)) {
            
            batch.codes[i].commissionCfa = commissionAmount;
            totalCommission += commissionAmount;
            updatedCount++;
            batchModified = true;
          }
        }
        
        if (batchModified) {
          await batch.save();
        }
      }
      
      console.log(`💰 Commissions recalculées: ${updatedCount} cartes × ${commissionAmount} FCFA = ${totalCommission} FCFA`);
      
      res.json({ 
        message: `Commissions recalculées avec succès`,
        updatedCards: updatedCount,
        commissionPerCard: commissionAmount,
        totalCommission: totalCommission
      });
    } catch (error) {
      console.error("Erreur recalcul commissions:", error);
      res.status(500).json({ message: "Erreur serveur lors du recalcul des commissions" });
    }
  }
);


module.exports = router;
