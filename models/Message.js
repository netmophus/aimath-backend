const mongoose = require("mongoose");

const messageSchema = new mongoose.Schema(
  {
    from: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User", // l’expéditeur
      required: true,
    },
    to: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User", // le destinataire
      required: true,
    },
    text: {
      type: String,
      default: "",
    },
    fileUrl: {
      type: String,
      default: "", // lien vers un fichier (PDF, image, etc.)
    },
    fileType: {
      type: String,
     enum: ["", "image", "pdf", "audio", "video"],
      default: "",
    },
    isVoiceMessage: {
      type: Boolean,
      default: false,
    },
    read: {
      type: Boolean,
      default: false,
    },
    isDeleted: {
      type: Boolean,
      default: false,
    },
    deletedAt: {
      type: Date,
      default: null,
    },
    deletedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      default: null,
    },
  },
  {
    timestamps: true, // createdAt pour l'ordre chronologique
  }
);

module.exports = mongoose.model("Message", messageSchema);
