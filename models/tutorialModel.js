const mongoose = require("mongoose");

const tutorialSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: [true, "Le titre est requis"],
      trim: true,
    },
    description: {
      type: String,
      required: [true, "La description est requise"],
      trim: true,
    },
    videoUrl: {
      type: String,
      required: [true, "L'URL de la vidéo est requise"],
      trim: true,
    },
    videoType: {
      type: String,
      enum: ["vimeo"],
      default: "vimeo",
      required: true,
    },
    icon: {
      type: String,
      required: true,
      enum: [
        "PersonAdd",
        "CreditCard",
        "ChatBubbleOutline",
        "CameraAlt",
        "School",
        "MenuBook",
        "PlayCircleOutline",
        "Assignment",
        "HelpOutline",
      ],
      default: "HelpOutline",
    },
    color: {
      type: String,
      required: true,
      default: "#2196F3",
    },
    order: {
      type: Number,
      required: true,
      default: 0,
    },
    isActive: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: true,
  }
);

// Index pour trier par ordre
tutorialSchema.index({ order: 1 });

module.exports = mongoose.model("Tutorial", tutorialSchema);

