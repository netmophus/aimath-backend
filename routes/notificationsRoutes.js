


const express = require('express');
const mongoose = require('mongoose');
const router = express.Router();
const Notification = require('../models/Notification');
const User = require('../models/userModel'); // ⚠️ chemin cohérent avec ton projet

// Cast sûr en ObjectId
const toObjectId = (id) =>
  mongoose.Types.ObjectId.isValid(id) ? new mongoose.Types.ObjectId(id) : null;

// Petit helper d'affichage des types contenus dans un array d'IDs
const showIdTypes = (arr = []) =>
  arr.map((x) => (x && x.constructor ? x.constructor.name : typeof x));

/* -------------------------------------------
 * GET /api/notifications/unread/:userId
 * ----------------------------------------- */
// router.get('/unread/:userId', async (req, res) => {
//   const { userId } = req.params;
//   if (!userId) return res.status(400).json({ message: 'userId requis' });

//   const uid = toObjectId(userId);
//   if (!uid) return res.status(400).json({ message: 'userId invalide' });
//   const uidStr = String(uid);

//   try {
//     const limit = Math.min(parseInt(req.query.limit || '50', 10), 100);
//     const skip  = Math.max(parseInt(req.query.skip  || '0', 10), 0);

//     const filter = {
//       $or: [{ userId: null }, { userId: uid }],
//       // Double $nin pour gérer ObjectId et d'anciens strings
//       $and: [
//         { isReadBy: { $nin: [uid] } },
//         { isReadBy: { $nin: [uidStr] } },
//       ],
//     };

//     console.log('🔎 [GET /unread] uid=', uidStr, 'limit=', limit, 'skip=', skip);

//     const [notifications, unreadCount] = await Promise.all([
//       Notification.find(filter)
//         .sort({ createdAt: -1 })
//         .skip(skip)
//         .limit(limit)
//         .select('_id title message linkTo createdAt isReadBy')
//         .lean(),
//       Notification.countDocuments(filter),
//     ]);

//     // Log rapide des types d'IDs présents
//     console.log(
//       '📬 [GET /unread] count=',
//       unreadCount,
//       ' sampleTypes=',
//       notifications[0]?.isReadBy ? showIdTypes(notifications[0].isReadBy) : []
//     );

//     // On n'expose pas isReadBy au client
//     const sanitized = notifications.map(({ isReadBy, ...rest }) => rest);

//     res.json({ unreadCount, notifications: sanitized });
//   } catch (err) {
//     console.error('💥 [GET /unread] Erreur:', err?.message, err?.stack);
//     res.status(500).json({ message: 'Erreur serveur', error: err?.message });
//   }
// });



router.get('/unread/:userId', async (req, res) => {
  const { userId } = req.params;
  if (!userId) return res.status(400).json({ message: 'userId requis' });

  const uid = toObjectId(userId);
  if (!uid) return res.status(400).json({ message: 'userId invalide' });
  const uidStr = String(uid);

  try {
    // 🔎 Récupère l’utilisateur (createdAt existe déjà grâce à timestamps)
    const user = await User.findById(uid).select('createdAt firstLoginAt');
    if (!user) return res.status(404).json({ message: 'Utilisateur introuvable' });

    // 🎯 baseline robuste : firstLoginAt si présent, sinon createdAt
    const baseline = user.firstLoginAt || user.createdAt;

    const limit = Math.min(parseInt(req.query.limit || '50', 10), 100);
    const skip  = Math.max(parseInt(req.query.skip  || '0', 10), 0);

    const filter = {
      $or: [{ userId: null }, { userId: uid }],
      $and: [
        { isReadBy: { $nin: [uid] } },
        { isReadBy: { $nin: [uidStr] } },
      ],
      // 🧹 coupe le passé pour ce user
      createdAt: { $gte: baseline },
    };

    const [notifications, unreadCount] = await Promise.all([
      Notification.find(filter)
        .sort({ createdAt: -1 })
        .skip(skip)
        .limit(limit)
        .select('_id title message linkTo createdAt isReadBy')
        .lean(),
      Notification.countDocuments(filter),
    ]);

    const sanitized = notifications.map(({ isReadBy, ...rest }) => rest);
    res.json({ unreadCount, notifications: sanitized });
  } catch (err) {
    console.error('💥 [GET /unread] Erreur:', err?.message, err?.stack);
    res.status(500).json({ message: 'Erreur serveur', error: err?.message });
  }
});

/* -------------------------------------------------
 * POST /api/notifications/mark-as-read/:notificationId
 * ------------------------------------------------ */
router.post('/mark-as-read/:notificationId', async (req, res) => {
  const { notificationId } = req.params;
  const { userId } = req.body;

  console.log('➡️ [POST mark-as-read] notifId=', notificationId, 'body=', req.body);

  if (!userId) return res.status(400).json({ message: 'userId requis' });
  if (!mongoose.Types.ObjectId.isValid(notificationId)) {
    return res.status(400).json({ message: 'notificationId invalide' });
  }

  const uid = toObjectId(userId);
  if (!uid) return res.status(400).json({ message: 'userId invalide' });

  try {
    // Avant maj : voir ce qu'on a
    const before = await Notification.findById(notificationId).select('isReadBy userId');
    if (!before) {
      console.log('❔ [POST mark-as-read] Notification introuvable');
      return res.status(404).json({ message: 'Notification introuvable' });
    }
    console.log(
      '👀 [POST mark-as-read] before types=',
      showIdTypes(before.isReadBy),
      ' values=',
      before.isReadBy?.map((x) => String(x))
    );

    // Ajout idempotent de l'ObjectId
    const upd = await Notification.updateOne(
      { _id: notificationId },
      { $addToSet: { isReadBy: uid } }
    );

    console.log('🛠️ [POST mark-as-read] updateOne =>', upd);

    // Après maj : vérifier contenu
    const after = await Notification.findById(notificationId).select('isReadBy');
    console.log(
      '✅ [POST mark-as-read] after types=',
      showIdTypes(after.isReadBy),
      ' values=',
      after.isReadBy?.map((x) => String(x))
    );

    // Recalcule du compteur fiable (ObjectId + string)
    const uidStr = String(uid);
    const filter = {
      $or: [{ userId: null }, { userId: uid }],
      $and: [
        { isReadBy: { $nin: [uid] } },
        { isReadBy: { $nin: [uidStr] } },
      ],
    };
    const unreadCount = await Notification.countDocuments(filter);
    console.log('🔢 [POST mark-as-read] unreadCount=', unreadCount);

    res.json({ message: 'Notification marquée comme lue', unreadCount });
  } catch (err) {
    console.error('💥 [POST mark-as-read] Erreur:', err?.message, err?.stack);
    res.status(500).json({ message: 'Erreur serveur', error: err?.message });
  }
});

module.exports = router;
