const express = require("express");
const router = express.Router();
const { createAdmin, createRechargeCode, getAllUsers, toggleUserStatus, getAdminStats } = require("../controllers/adminController");
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


router.get("/users", 
   authMiddleware,
  authorizeRoles("admin"),  
  getAllUsers);  
  
  
  
router.put("/users/:id/toggle", 
   authMiddleware,
  authorizeRoles("admin"),  
  toggleUserStatus); 

router.get("/stats", authMiddleware, authorizeRoles("admin"), getAdminStats);


module.exports = router;
