const mongoose = require("mongoose");

const otpSchema = new mongoose.Schema({
  phone: { type: String, sparse: true },
  email: { type: String, sparse: true, lowercase: true },
  otp: { type: String, required: true },
  expiresAt: { type: Date, required: true },
  createdAt: { type: Date, default: Date.now },
});

// Index TTL pour supprimer automatiquement les OTP expirés après 5 minutes
otpSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 });

// Index pour garantir l'unicité par phone ou email
otpSchema.index({ phone: 1 }, { unique: true, sparse: true });
otpSchema.index({ email: 1 }, { unique: true, sparse: true });

module.exports = mongoose.model("OTP", otpSchema);



