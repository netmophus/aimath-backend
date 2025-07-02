const mongoose = require("mongoose");

const videoSchema = new mongoose.Schema(
  {
    title: { type: String, required: true, trim: true },
    description: { type: String, required: true },
    level: { type: String, required: true }, // ex: "6eme", "terminale", "universite"
    badge: {
      type: String,
      enum: ["gratuit", "prenuim"],
      default: "gratuit",
    },
    videoUrl: { type: String, required: true }, // Lien de la vidéo (YouTube, Vimeo, Cloudinary...)
    thumbnail: { type: String, required: false }, // Optionnel : image d’aperçu
  },
  { timestamps: true }
);

module.exports = mongoose.model("Video", videoSchema);
