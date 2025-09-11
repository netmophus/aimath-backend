const mongoose = require("mongoose");

// models/PaymentHistory.js (ou équivalent)
const paymentSchema = new mongoose.Schema({
  user:   { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
  phone:  { type: String, required: true },
  amount: { type: Number, default: 2000 },    // ← plus "required: true"
  reference: { type: String },
  paidAt: { type: Date, default: Date.now }
});


module.exports = mongoose.model("Payment", paymentSchema);
