const mongoose = require("mongoose");

const examSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: true,
      trim: true,
    },
    level: {
      type: String,
      required: true, // Exemple : "3eme", "terminale", etc.
    },
    description: {
      type: String,
      required: true,
    },
    badge: {
      type: String,
      enum: ["gratuit", "prenuim"],
      default: "gratuit",
    },
  subjectUrl: {
      type: String,
      required: true, // URL du fichier sujet
    },
   correctionUrl: {
      type: String, // ✅ Plus requis
      default: null,
    },
    coverImage: {
      type: String, // Optionnel, pour une miniature
    },

    subjectDownloadCount: {
  type: Number,
  default: 0,
},
correctionDownloadCount: {
  type: Number,
  default: 0,
},

  },
  { timestamps: true }
);

module.exports = mongoose.model("Exam", examSchema);
