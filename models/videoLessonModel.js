const mongoose = require("mongoose");

const videoLessonSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: true,
      trim: true,
    },
    chapter: {
      type: String,
      required: true, // Exemple : "Chapitre 1 : Les Nombres"
    },
    level: {
      type: String,
      required: true, // Exemple : "6eme", "terminale", "universite"
    },
    subject: {
      type: String,
      default: "Mathématiques",
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
    videoUrl: {
      type: String,
      required: true, // Lien YouTube ou lien direct
    },
    thumbnail: {
      type: String,
      default: "", // Miniature facultative
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model("VideoLesson", videoLessonSchema);
