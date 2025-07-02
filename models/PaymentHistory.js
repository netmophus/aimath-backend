const mongoose = require("mongoose");

const paymentSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
  phone: { type: String, required: true },
  amount: { type: Number, required: true },
  reference: { type: String },
  paidAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model("Payment", paymentSchema);
