const MessageNotification = require("../models/MessageNotification");

// 📥 Obtenir toutes les notifications non lues
const getUnreadNotifications = async (req, res) => {
  const userId = req.user._id;
  console.log("📦 [MessageNotif] ID utilisateur :", userId); // ✅ log de l'utilisateur

  try {
    // const notifications = await MessageNotification.find({
    //   user: userId,
    //   isRead: false,
    // }).sort({ createdAt: -1 });


    const notifications = await MessageNotification.find({
        user: req.user._id,
        isRead: false,
        })
        .populate('from', 'fullName phone') // ✅ C’est ici qu’on ajoute les infos de l’expéditeur
        .sort({ createdAt: -1 });


    console.log("📬 [MessageNotif] Nombre de notifications non lues :", notifications.length);
    res.json(notifications);
  } catch (error) {
    console.error("❌ [MessageNotif] Erreur récupération notifications :", error.message);
    res.status(500).json({ message: "Erreur serveur" });
  }
};


// ✅ Marquer une notification spécifique comme lue
// const markNotificationAsRead = async (req, res) => {
//   try {
//     const notification = await MessageNotification.findByIdAndUpdate(
//       req.params.id,
//       { isRead: true },
//       { new: true }
//     );
//     res.status(200).json(notification);
//   } catch (error) {
//     res.status(500).json({ message: "Erreur lors de la mise à jour de la notification." });
//   }
// };

// ✅ Marquer une notification spécifique comme lue (sécurisé)
const markNotificationAsRead = async (req, res) => {
  try {
    const { id } = req.params;          // ID de la notif
    const userId = req.user._id;        // user connecté

    const notification = await MessageNotification.findOneAndUpdate(
      { _id: id, user: userId },        // 👈 n'update que si la notif appartient au user
      { $set: { isRead: true } },
      { new: true }
    ).populate('from', 'fullName phone');

    if (!notification) {
      return res
        .status(404)
        .json({ message: "Notification introuvable ou non autorisée." });
    }

    return res.status(200).json(notification);
  } catch (error) {
    console.error("Erreur markNotificationAsRead:", error);
    return res
      .status(500)
      .json({ message: "Erreur lors de la mise à jour de la notification." });
  }
};




// ✅ Marquer toutes les notifications comme lues pour un utilisateur
const markAllNotificationsAsRead = async (req, res) => {
  try {
    await MessageNotification.updateMany(
      { user: req.user._id, isRead: false },
      { isRead: true }
    );
    res.status(200).json({ message: "Toutes les notifications ont été lues." });
  } catch (error) {
    res.status(500).json({ message: "Erreur lors de la mise à jour des notifications." });
  }
};



const markNotificationsFromUserAsRead = async (req, res) => {
  try {
    await MessageNotification.updateMany(
      {
        user: req.user._id,      // l'enseignant connecté
        from: req.params.userId, // l'élève dont on lit les messages
        isRead: false,
      },
      { isRead: true }
    );

    res.status(200).json({ message: "Notifications marquées comme lues." });
  } catch (error) {
    res.status(500).json({ message: "Erreur lors de la mise à jour." });
  }
};


module.exports = {
  getUnreadNotifications,
  markNotificationAsRead,
  markAllNotificationsAsRead,
  markNotificationsFromUserAsRead,
};
