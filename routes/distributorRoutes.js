// routes/distributorRoutes.js
const express = require("express");
const router = express.Router();

const {
  createDistributor,
  listDistributors,
  getDistributorById,
  updateDistributor,
  deleteDistributor,
  listNearbyDistributors,
} = require("../controllers/distributorController");

const auth = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

/**
 * GET — Public (listing / détail / near)
 */
router.get("/", listDistributors);
router.get("/near", listNearbyDistributors);
router.get("/:id", getDistributorById);

/**
 * POST/PUT/PATCH/DELETE — Admin uniquement
 */
router.post("/", auth, authorizeRoles("admin"), createDistributor);
router.put("/:id", auth, authorizeRoles("admin"), updateDistributor);
router.patch("/:id", auth, authorizeRoles("admin"), updateDistributor);
router.delete("/:id", auth, authorizeRoles("admin"), deleteDistributor);

module.exports = router;
