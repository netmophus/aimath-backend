const mongoose = require("mongoose");

const examPaperSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: true,
      trim: true,
    },
    level: {
      type: String,
      required: true, // "3eme", "terminale", etc.
    },
    year: {
      type: String,
      required: true, // Exemple : "2022"
    },
    description: {
      type: String,
      default: "",
    },
    badge: {
      type: String,
      enum: ["gratuit", "prenuim"],
      default: "gratuit",
    },
    fileUrl: {
      type: String,
      required: true, // Lien vers le fichier PDF
    },
    correctionUrl: {
      type: String,
      default: "", // Optionnel : lien PDF ou vidéo de correction
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model("ExamPaper", examPaperSchema);
