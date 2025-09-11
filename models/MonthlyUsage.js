const mongoose = require("mongoose");

const monthlyUsageSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
  period: { type: String, required: true }, // ex: "2025-07"
  booksDownloaded: { type: Number, default: 0 },
  videosWatched: { type: Number, default: 0 },
  iaGptVisionQuestions: { type: Number, default: 0 },

  examsDownloaded: { type: Number, default: 0 },
  examsCorrectionsDownloaded: { type: Number, default: 0 }, // ✅ nouveau champ

  iaTextQuestions: { type: Number, default: 0 },     // ✅ Nouveau champ pour les questions texte
  iaImageQuestions: { type: Number, default: 0 },    // ✅ Nouveau champ pour les questions image

  supportRequestsCreated:  { type: Number, default: 0 }, // nb de requêtes que l'élève a créées ce mois
  supportRequestsAccepted: { type: Number, default: 0 }, // nb de requêtes acceptées par un prof (stat)
  supportRequestsFinished: { type: Number, default: 0 }, // nb de requêtes terminées (stat)


}, { timestamps: true });

monthlyUsageSchema.index({ user: 1, period: 1 }, { unique: true });

module.exports = mongoose.model("MonthlyUsage", monthlyUsageSchema);

