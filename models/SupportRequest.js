const mongoose = require("mongoose");

const supportRequestSchema = new mongoose.Schema(
  {
    student: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },

    sessionStarted: {
  type: Boolean,
  default: false,
},
    teacher: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: false, // si l’élève ne choisit pas encore d’enseignant
    },
    topic: {
      type: String,
      required: true,
    },

    description: {
      type: String,
      default: "", // Détails supplémentaires optionnels
    },


    level: {
      type: String,
      required: true, // ex: "3e", "4e"
    },
    serie: {
  type: String,
  enum: ["", "A", "C", "D", "E", "F", "G"],
  default: "", // vide si non concerné (collège)
},

    type: {
      type: String,
      enum: ["chat", "visio"],
      default: "chat",
    },
   status: {
  type: String,
  enum: ["en_attente", "acceptee", "refusee", "terminee"],
  default: "en_attente",
}, 



  // --- Champs optionnels pour le suivi et la rémunération ---
   awardedPoints:   { type: Number,  default: 0 },
   countedForPayout:{ type: Boolean, default: false, index: true },
   payoutMonth:     { type: String,  default: "" },   // ex: "2025-09"
   completedAt:     { type: Date },



  },
  {
    timestamps: true, // createdAt, updatedAt
  }
);

module.exports = mongoose.model("SupportRequest", supportRequestSchema);
