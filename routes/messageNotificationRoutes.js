const express = require("express");
const router = express.Router();
const {
  getUnreadNotifications,
  markNotificationAsRead,
  markAllNotificationsAsRead,
   markNotificationsFromUserAsRead,
} = require("../controllers/messageNotificationController");

const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// 📥 Récupérer toutes les notifications non lues pour l’utilisateur connecté
router.get("/unread",authMiddleware, getUnreadNotifications);

// ✅ Marquer une notification comme lue
router.put("/:id/read", authMiddleware, markNotificationAsRead);

// ✅ Marquer toutes les notifications de l'utilisateur comme lues
router.put("/read/all", authMiddleware, markAllNotificationsAsRead);

router.put("/read/from/:userId", authMiddleware, markNotificationsFromUserAsRead);


module.exports = router;
