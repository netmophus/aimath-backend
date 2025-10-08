// models/ContentRequest.js
const mongoose = require("mongoose");

const contentRequestSchema = new mongoose.Schema(
  {
    student: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    
    // Type de contenu demandé
    contentType: {
      type: String,
      enum: ["video", "livre", "exercices", "fiche", "autre"],
      required: true,
    },
    
    // Matière
    subject: {
      type: String,
      enum: ["maths", "physique", "chimie", "svt"],
      default: "maths",
      required: true,
    },
    
    // Niveau scolaire
    level: {
      type: String,
      required: true,
    },
    
    // Chapitre / Thème
    chapter: {
      type: String,
      trim: true,
    },
    
    // Description détaillée
    description: {
      type: String,
      required: true,
      trim: true,
    },
    
    // Priorité (1-5, 5 = urgent)
    priority: {
      type: Number,
      default: 3,
      min: 1,
      max: 5,
    },
    
    // Statut de la demande
    status: {
      type: String,
      enum: ["en_attente", "en_cours", "terminee", "annulee"],
      default: "en_attente",
    },
    
    // Notes de l'admin
    adminNotes: {
      type: String,
      trim: true,
    },
    
    // Date de traitement
    processedAt: {
      type: Date,
    },
    
    // Traité par (admin)
    processedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
    },
    
    // Email envoyé
    emailSent: {
      type: Boolean,
      default: false,
    },
  },
  { timestamps: true }
);

// Index pour recherche
contentRequestSchema.index({ student: 1, status: 1 });
contentRequestSchema.index({ status: 1, createdAt: -1 });

module.exports = mongoose.model("ContentRequest", contentRequestSchema);

