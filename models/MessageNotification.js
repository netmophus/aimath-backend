// const mongoose = require("mongoose");

// const messageNotificationSchema = new mongoose.Schema(
//   {
//     user: {
//       type: mongoose.Schema.Types.ObjectId,
//       ref: "User",          // 📥 Utilisateur concerné par la notif (le destinataire)
//       required: true,
//     },
//     from: {
//       type: mongoose.Schema.Types.ObjectId,
//       ref: "User",          // ✉️ L’expéditeur du message
//       required: true,
//     },
//     conversationId: {
//       type: mongoose.Schema.Types.ObjectId,
//       ref: "Conversation", // 🔁 Optionnel si tu gères des conversations groupées
//     },
//     messageId: {
//       type: mongoose.Schema.Types.ObjectId,
//       ref: "Message",       // 📩 Référence au message non lu
//     },
//     messageSnippet: {
//       type: String,         // 🔤 Un petit aperçu du message (30-50 caractères)
//     },
//     isRead: {
//       type: Boolean,
//       default: false,
//     },
//   },
//   { timestamps: true }
// );

// module.exports = mongoose.model("MessageNotification", messageNotificationSchema);




const mongoose = require("mongoose");

const messageNotificationSchema = new mongoose.Schema(
  {
    user: { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
    from: { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
    conversationId: { type: mongoose.Schema.Types.ObjectId, ref: "Conversation" },
    messageId: { type: mongoose.Schema.Types.ObjectId, ref: "Message" },
    messageSnippet: { type: String },
    isRead: { type: Boolean, default: false },
  },
  { timestamps: true }
);

/* 🔎 Index pour accélérer:
   - la récup des non-lues par user
   - le marquage en lot par expéditeur
   - le tri récent
*/
messageNotificationSchema.index({ user: 1, isRead: 1, from: 1, createdAt: -1 });

// (optionnel) autre index utile pour liste simple par user
// messageNotificationSchema.index({ user: 1, createdAt: -1 });

module.exports = mongoose.model("MessageNotification", messageNotificationSchema);
