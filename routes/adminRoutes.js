const express = require("express");
const router = express.Router();
const { createAdmin, createRechargeCode, getAllUsers, toggleUserStatus, getAdminStats } = require("../controllers/adminController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const User = require("../models/userModel");
router.post("/create", createAdmin);


const mongoose = require("mongoose");


const AccessCodeBatch = require("../models/AccessCodeBatch");



// ✅ Créer un code de recharge (admin uniquement)
router.post(
  "/recharge-code",
  authMiddleware,
  authorizeRoles("admin"),
  createRechargeCode
);


router.get("/users", 
   authMiddleware,
  authorizeRoles("admin"),  
  getAllUsers);  
  
  
  
router.put("/users/:id/toggle", 
   authMiddleware,
  authorizeRoles("admin"),  
  toggleUserStatus); 

router.get("/stats", authMiddleware, authorizeRoles("admin"), getAdminStats);


// POST /api/admin/partners
router.post("/partners", authMiddleware, authorizeRoles("admin"), async (req, res) => {
  try {
    const {
      fullName, phone, password, passwordConfirm,
      companyName, region, commissionDefaultCfa
    } = req.body;

    const u = await User.create({
      fullName,
      phone,
      password,
      passwordConfirm,
      role: "partner",
      companyName: companyName || "",
      region: region || "",
      commissionDefaultCfa: Number(commissionDefaultCfa || 0),
    });

    res.status(201).json({
      _id: u._id,
      fullName: u.fullName,
      phone: u.phone,
      role: u.role,
      companyName: u.companyName,
      region: u.region,
      commissionDefaultCfa: u.commissionDefaultCfa,
      createdAt: u.createdAt,
    });
  } catch (e) {
    if (e?.code === 11000 && e?.keyPattern?.phone) {
      return res.status(409).json({ message: "Un utilisateur avec ce téléphone existe déjà." });
    }
    console.error("create partner error:", e);
    res.status(400).json({ message: e.message || "Erreur création partenaire." });
  }
});

// GET /api/admin/partners (inchangé)
router.get("/partners", authMiddleware, authorizeRoles("admin"), async (_req, res) => {
  try {
    const rows = await User.find({ role: "partner" })
      .select("_id fullName phone companyName region commissionDefaultCfa createdAt")
      .sort({ createdAt: -1 });
    res.json(rows);
  } catch (e) {
    console.error("list partners error:", e);
    res.status(500).json({ message: "Erreur de chargement des partenaires." });
  }
});



// GET /api/admin/partners/:partnerId/codes?status=all|activated|used
// GET /api/admin/partners/:partnerId/codes?status=all|activated|used
router.get(
  "/partners/:partnerId/codes",
  authMiddleware,
  authorizeRoles("admin"),
  async (req, res) => {
    try {
      const { partnerId } = req.params;
      const status = String(req.query.status || "all").toLowerCase();

      // 1) Validate ObjectId
      if (!mongoose.Types.ObjectId.isValid(partnerId)) {
        return res.status(400).json({ message: "partnerId invalide." });
      }
      const partnerObjId = new mongoose.Types.ObjectId(partnerId);

      // 2) (Optionnel) check que le partenaire existe
      const partnerExists = await User.exists({ _id: partnerObjId, role: "partner" });
      if (!partnerExists) {
        return res.status(404).json({ message: "Partenaire introuvable." });
      }

      // 3) Build pipeline
      const matchStatus =
        status !== "all" ? { "codes.status": status } : {};

      const pipeline = [
        { $match: { "codes.partner": partnerObjId } },
        { $unwind: "$codes" },
        { $match: { "codes.partner": partnerObjId, ...matchStatus } },
        {
          $project: {
            _id: 0,
            batchId: "$batchId",
            type: "$type",
            faceValueCfa: { $ifNull: ["$codes.price", "$price"] },
            code: "$codes.code",
            status: "$codes.status", // generated | activated | used
            assignedAt: "$codes.assignedAt",
            activatedAt: "$codes.activatedAt",
            soldAt: "$codes.soldAt",
            usedAt: "$codes.usedAt",
            commissionCfa: { $ifNull: ["$codes.commissionCfa", 0] }
          }
        },
        {
          $sort: {
            // tri par date la plus récente connue
            assignedAt: -1,
            activatedAt: -1,
            soldAt: -1,
            usedAt: -1
          }
        }
      ];

      const items = await AccessCodeBatch.aggregate(pipeline);
      return res.json({ count: items.length, items });
    } catch (e) {
      console.error("admin get partner codes error:", e);
      return res.status(500).json({ message: "Erreur serveur." });
    }
  }
);




module.exports = router;
