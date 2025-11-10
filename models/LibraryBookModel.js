const mongoose = require("mongoose");

const libraryBookSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: [true, "Le titre du livre est requis"],
      trim: true,
      maxlength: [200, "Le titre ne peut pas dépasser 200 caractères"],
    },
    author: {
      type: String,
      required: [true, "L'auteur est requis"],
      trim: true,
      maxlength: [100, "Le nom de l'auteur ne peut pas dépasser 100 caractères"],
    },
    description: {
      type: String,
      required: [true, "La description est requise"],
      trim: true,
      maxlength: [1000, "La description ne peut pas dépasser 1000 caractères"],
    },
    summary: {
      type: [String],
      required: [true, "Le sommaire est requis"],
      validate: {
        validator: function (summary) {
          return summary && summary.length > 0;
        },
        message: "Le sommaire doit contenir au moins un chapitre",
      },
    },
    subject: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "LibrarySubject",
      required: [true, "La matière est requise"],
    },
    level: {
      type: String,
      required: [true, "Le niveau est requis"],
      enum: ["universite"], // Uniquement université
    },
    pages: {
      type: Number,
      required: [true, "Le nombre de pages est requis"],
      min: [1, "Le livre doit avoir au moins 1 page"],
      max: [5000, "Le livre ne peut pas dépasser 5000 pages"],
    },
    year: {
      type: Number,
      required: [true, "L'année de publication est requise"],
      min: [1900, "L'année doit être supérieure à 1900"],
      max: [new Date().getFullYear() + 1, "L'année ne peut pas être dans le futur"],
    },
    coverImageUrl: {
      type: String,
      required: [true, "L'URL de la page de couverture est requise"],
      trim: true,
      validate: {
        validator: function (v) {
          return /^https?:\/\/.+/.test(v);
        },
        message: "L'URL de la page de couverture doit être valide",
      },
    },
    summaryUrl: {
      type: String,
      required: [true, "L'URL du sommaire est requise"],
      trim: true,
      validate: {
        validator: function (v) {
          return /^https?:\/\/.+/.test(v);
        },
        message: "L'URL du sommaire doit être valide",
      },
    },
    isAvailable: {
      type: Boolean,
      default: true,
    },
    downloads: {
      type: Number,
      default: 0,
      min: [0, "Le nombre de téléchargements ne peut pas être négatif"],
    },
    views: {
      type: Number,
      default: 0,
      min: [0, "Le nombre de vues ne peut pas être négatif"],
    },
    tags: {
      type: [String],
      default: [],
      validate: {
        validator: function (tags) {
          return tags.length <= 10;
        },
        message: "Maximum 10 tags autorisés",
      },
    },
    language: {
      type: String,
      default: "fr",
      enum: ["fr", "en", "ar"],
    },
    addedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: [true, "L'utilisateur qui a ajouté le livre est requis"],
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
libraryBookSchema.index({ title: "text", author: "text", description: "text" });
libraryBookSchema.index({ subject: 1, level: 1 });
libraryBookSchema.index({ downloads: -1, views: -1 });
libraryBookSchema.index({ isAvailable: 1 });

// Méthode pour incrémenter les vues
libraryBookSchema.methods.incrementViews = function () {
  this.views += 1;
  return this.save();
};

// Méthode pour incrémenter les téléchargements
libraryBookSchema.methods.incrementDownloads = function () {
  this.downloads += 1;
  return this.save();
};

// Méthode statique pour rechercher des livres
libraryBookSchema.statics.searchBooks = function (query, options = {}) {
  const {
    subject,
    level,
    page = 1,
    limit = 12,
    sortBy = "createdAt",
    sortOrder = -1,
  } = options;

  const filter = {};

  if (query) {
    filter.$or = [
      { title: { $regex: query, $options: "i" } },
      { author: { $regex: query, $options: "i" } },
      { description: { $regex: query, $options: "i" } },
      { summary: { $regex: query, $options: "i" } },
    ];
  }

  if (subject) {
    filter.subject = subject;
  }

  if (level) {
    filter.level = level;
  }

  const skip = (page - 1) * limit;
  const sort = { [sortBy]: sortOrder };

  return this.find(filter)
    .sort(sort)
    .skip(skip)
    .limit(limit)
    .populate("subject", "name color icon")
    .populate("addedBy", "name email");
};

// Méthode statique pour obtenir les livres populaires
libraryBookSchema.statics.getPopularBooks = function (limit = 10) {
  return this.find({ isAvailable: true })
    .sort({ downloads: -1, views: -1 })
    .limit(limit)
    .populate("subject", "name color icon")
    .populate("addedBy", "name email");
};

// Middleware pour mettre à jour lastModified avant la sauvegarde
libraryBookSchema.pre("save", function (next) {
  this.lastModified = new Date();
  next();
});

module.exports = mongoose.model("LibraryBook", libraryBookSchema);
