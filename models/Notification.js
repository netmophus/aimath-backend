// const mongoose = require('mongoose');

// const notificationSchema = new mongoose.Schema({
//   userId: {
//     type: mongoose.Schema.Types.ObjectId,
//     ref: 'User',
//     required: false, // null si c'est une notif globale
//   },
//   title: String,
//   type: {
//     type: String,
//     enum: ['content', 'chat'],
//     default: 'content',
//   },
//   linkTo: String, // ex: /livres/123
//   isReadBy: {
//     type: [mongoose.Schema.Types.ObjectId], // liste des utilisateurs qui ont lu
//     default: [],
//   },
//   createdAt: {
//     type: Date,
//     default: Date.now,
//   },
// });

// module.exports = mongoose.model('Notification', notificationSchema);








// models/Notification.js
const mongoose = require('mongoose');

const notificationSchema = new mongoose.Schema({
  // null = notification générale
  userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', default: null, index: true },

  title:   { type: String, required: true },
  message: { type: String, default: '' },

  type:   { type: String, enum: ['content', 'chat'], default: 'content' },
  linkTo: { type: String, default: '' }, // ex: "ExamList"

  // Toujours en ObjectId (plus de strings)
  isReadBy: [{ type: mongoose.Schema.Types.ObjectId, ref: 'User', index: true }],

  createdAt: { type: Date, default: Date.now },
});

// Index utiles
notificationSchema.index({ userId: 1, createdAt: -1 });
notificationSchema.index({ isReadBy: 1 });

module.exports = mongoose.model('Notification', notificationSchema);
