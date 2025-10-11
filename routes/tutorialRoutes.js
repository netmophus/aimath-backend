const express = require("express");
const router = express.Router();
const {
  getAllTutorials,
  getAllTutorialsAdmin,
  getTutorialById,
  createTutorial,
  updateTutorial,
  deleteTutorial,
  toggleTutorialStatus,
} = require("../controllers/tutorialController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// Routes publiques
router.get("/", getAllTutorials);

// Routes admin
router.get("/admin/all", authMiddleware, authorizeRoles("admin"), getAllTutorialsAdmin);
router.get("/:id", authMiddleware, authorizeRoles("admin"), getTutorialById);
router.post("/", authMiddleware, authorizeRoles("admin"), createTutorial);
router.put("/:id", authMiddleware, authorizeRoles("admin"), updateTutorial);
router.delete("/:id", authMiddleware, authorizeRoles("admin"), deleteTutorial);
router.patch("/:id/toggle", authMiddleware, authorizeRoles("admin"), toggleTutorialStatus);

module.exports = router;

