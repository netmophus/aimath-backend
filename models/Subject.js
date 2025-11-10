const mongoose = require("mongoose");

const subjectSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: [true, "Le nom de la matière est requis"],
      trim: true,
      unique: true,
      maxlength: [100, "Le nom de la matière ne peut pas dépasser 100 caractères"],
    },
    description: {
      type: String,
      required: [true, "La description est requise"],
      trim: true,
      maxlength: [500, "La description ne peut pas dépasser 500 caractères"],
    },
    color: {
      primary: {
        type: String,
        required: [true, "La couleur primaire est requise"],
        match: [/^#[0-9A-Fa-f]{6}$/, "Format de couleur invalide (hex)"],
      },
      secondary: {
        type: String,
        required: [true, "La couleur secondaire est requise"],
        match: [/^#[0-9A-Fa-f]{6}$/, "Format de couleur invalide (hex)"],
      },
    },
    icon: {
      type: String,
      required: [true, "L'icône est requise"],
      trim: true,
    },
    isActive: {
      type: Boolean,
      default: true,
    },
    bookCount: {
      type: Number,
      default: 0,
      min: [0, "Le nombre de livres ne peut pas être négatif"],
    },
    createdBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: [true, "L'utilisateur qui a créé la matière est requis"],
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

// Index pour améliorer les performances
subjectSchema.index({ name: 1 });
subjectSchema.index({ isActive: 1 });
subjectSchema.index({ bookCount: -1 });

// Méthode pour incrémenter le nombre de livres
subjectSchema.methods.incrementBookCount = function () {
  this.bookCount += 1;
  return this.save();
};

// Méthode pour décrémenter le nombre de livres
subjectSchema.methods.decrementBookCount = function () {
  if (this.bookCount > 0) {
    this.bookCount -= 1;
    return this.save();
  }
  return Promise.resolve();
};

// Méthode statique pour obtenir les matières actives
subjectSchema.statics.getActiveSubjects = function () {
  return this.find({ isActive: true }).sort({ name: 1 });
};

// Middleware pour mettre à jour lastModified avant la sauvegarde
subjectSchema.pre("save", function (next) {
  this.lastModified = new Date();
  next();
});

module.exports = mongoose.model("LibrarySubject", subjectSchema);
