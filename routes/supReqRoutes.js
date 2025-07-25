const express = require("express");
const router = express.Router();
const {
  createSupportRequest,
  getStudentSupportRequests,
  getTeacherSupportRequests,
  updateSupportRequestStatus,
} = require("../controllers/supReqController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");


// 👨‍🎓 Créer une nouvelle demande de soutien (par un élève)
router.post("/", authMiddleware,  authorizeRoles("eleve"), createSupportRequest);

// 👨‍🎓 Voir mes propres demandes de soutien (élève)
router.get("/my", authMiddleware,  authorizeRoles("eleve"), getStudentSupportRequests);

// 👨‍🏫 Voir les demandes reçues (enseignant)
router.get("/teacher", authMiddleware,  authorizeRoles("eleve"), getTeacherSupportRequests);
 
// 🛠️ Mettre à jour le statut d’une demande (acceptée, refusée, etc.)
router.put("/:id/status", authMiddleware,  authorizeRoles("eleve"), updateSupportRequestStatus);

module.exports = router;
