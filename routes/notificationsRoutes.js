const express = require('express');
const router = express.Router();
const Notification = require('../models/Notification');

// GET /api/notifications/unread/:userId
router.get('/unread/:userId', async (req, res) => {
  const { userId } = req.params;

  try {
    const notifications = await Notification.find({
      $or: [
        { userId: null }, // notifs générales
        { userId },       // notifs ciblées
      ],
      isReadBy: { $ne: userId } // pas encore lues par ce user
    }).sort({ createdAt: -1 });

    res.json({
      unreadCount: notifications.length,
      notifications,
    });
  } catch (err) {
    console.error('Erreur API notifications :', err);
    res.status(500).json({ message: 'Erreur serveur' });
  }
});


// Marquer une notification comme lue
router.post('/mark-as-read/:notificationId', async (req, res) => {
  const { notificationId } = req.params;
  const { userId } = req.body;

  if (!userId) {
    return res.status(400).json({ message: 'userId requis' });
  }

  try {
    const notification = await Notification.findById(notificationId);

    if (!notification) {
      return res.status(404).json({ message: 'Notification introuvable' });
    }

    // Évite les doublons
    if (!notification.isReadBy.includes(userId)) {
      notification.isReadBy.push(userId);
      await notification.save();
    }

    res.json({ message: 'Notification marquée comme lue' });
  } catch (err) {
    console.error('Erreur lors du marquage :', err);
    res.status(500).json({ message: 'Erreur serveur' });
  }
});


module.exports = router;
