const mongoose = require("mongoose");

const rechargeCodeSchema = new mongoose.Schema({
  code: {
    type: String,
    required: true,
    unique: true,
  },
  value: {
    type: Number, // nombre de crédits à ajouter
    required: true,
  },
  type: {
    type: String,
    enum: ["credit", "abonnement"],
    default: "credit",
  },
  used: {
    type: Boolean,
    default: false,
  },
  usedBy: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    default: null,
  },
  usedAt: {
    type: Date,
  },
}, { timestamps: true });

module.exports = mongoose.model("RechargeCode", rechargeCodeSchema);
