const mongoose = require("mongoose");

const bookSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: true,
      trim: true,
    },
    author: {
      type: String,
      default: "",
      trim: true,
    },
    coverImage: {
      type: String,
      required: true, // URL de la photo de couverture
    },
    description: {
      type: String,
      required: true,
    },
    level: {
      type: String,
      required: true, // Exemple : "6eme", "terminale", "universite"
    },
    badge: {
      type: String,
      enum: ["gratuit", "prenuim"],
      default: "gratuit",
    },
    fileUrl: {
      type: String,
      required: true, // URL du fichier PDF du livre
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model("Book", bookSchema);
