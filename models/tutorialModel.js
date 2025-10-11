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
    youtubeId: {
      type: String,
      required: [true, "L'ID YouTube est requis"],
      trim: true,
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

