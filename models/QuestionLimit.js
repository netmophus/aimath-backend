const mongoose = require("mongoose");

const questionLimitSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: "User", unique: true },
  count: { type: Number, default: 0 },
  lastReset: { type: Date, default: Date.now },
});


module.exports = mongoose.model("QuestionLimit", questionLimitSchema);
