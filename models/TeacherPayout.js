const mongoose = require('mongoose');

const teacherPayoutSchema = new mongoose.Schema({
  teacher:       { type: mongoose.Schema.Types.ObjectId, ref: 'User', index: true, required: true },
  month:         { type: String, index: true, required: true }, // "YYYY-MM"
  points:        { type: Number, default: 0 },
  requestsCount: { type: Number, default: 0 },
  capCfa:        { type: Number, default: 25000 },
  payoutCfa:     { type: Number, default: 0 }, // calculé à chaque update
  isClosed:      { type: Boolean, default: false }, // si tu veux verrouiller en fin de mois
}, { timestamps: true });

teacherPayoutSchema.index({ teacher: 1, month: 1 }, { unique: true });

module.exports = mongoose.model('TeacherPayout', teacherPayoutSchema);
