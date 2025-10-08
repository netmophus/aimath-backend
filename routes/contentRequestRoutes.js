// routes/contentRequestRoutes.js
const express = require("express");
const router = express.Router();
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

const {
  createContentRequest,
  getMyContentRequests,
  getAllContentRequests,
  updateContentRequestStatus,
  deleteContentRequest,
} = require("../controllers/contentRequestController");

// ✅ Routes élève (premium uniquement)
router.post("/", authMiddleware, authorizeRoles("eleve"), createContentRequest);
router.get("/my-requests", authMiddleware, authorizeRoles("eleve"), getMyContentRequests);

// ✅ Routes admin
router.get("/all", authMiddleware, authorizeRoles("admin"), getAllContentRequests);
router.patch("/:id", authMiddleware, authorizeRoles("admin"), updateContentRequestStatus);
router.delete("/:id", authMiddleware, authorizeRoles("admin"), deleteContentRequest);

module.exports = router;
