const mongoose = require('mongoose');

const notificationSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: false, // null si c'est une notif globale
  },
  title: String,
  type: {
    type: String,
    enum: ['content', 'chat'],
    default: 'content',
  },
  linkTo: String, // ex: /livres/123
  isReadBy: {
    type: [mongoose.Schema.Types.ObjectId], // liste des utilisateurs qui ont lu
    default: [],
  },
  createdAt: {
    type: Date,
    default: Date.now,
  },
});

module.exports = mongoose.model('Notification', notificationSchema);
