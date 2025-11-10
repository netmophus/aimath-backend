const mongoose = require("mongoose");

const librarySubjectSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: [true, "Le nom de la matière est requis"],
      unique: true,
      trim: true,
      maxlength: [100, "Le nom ne peut pas dépasser 100 caractères"],
    },
    description: {
      type: String,
      trim: true,
      maxlength: [500, "La description ne peut pas dépasser 500 caractères"],
    },
    icon: {
      type: String,
      trim: true,
      default: "SchoolIcon", // Icône par défaut
    },
    color: {
      type: String,
      trim: true,
      default: "#3b82f6", // Couleur par défaut
    },
    addedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: [true, "L'utilisateur qui a ajouté la matière est requis"],
    },
    lastModified: {
      type: Date,
      default: Date.now,
    },
  },
  {
    timestamps: true,
  }
);

// Index pour améliorer les performances de recherche
librarySubjectSchema.index({ name: 1 });

// Middleware pour mettre à jour lastModified avant la sauvegarde
librarySubjectSchema.pre("save", function (next) {
  this.lastModified = new Date();
  next();
});

module.exports = mongoose.model("LibrarySubject", librarySubjectSchema);
