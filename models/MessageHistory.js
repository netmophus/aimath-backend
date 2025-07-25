const mongoose = require("mongoose");

const messageHistorySchema = new mongoose.Schema(
  {
    from: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    to: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    text: {
      type: String,
      default: "",
    },
    fileUrl: {
      type: String,
      default: "",
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
    originalRequest: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "SupportRequest", // référence vers la demande terminée
      required: true,
    },
    createdAt: {
      type: Date,
      required: true,
    },
  },
  {
    timestamps: false, // on garde uniquement le createdAt original du message
  }
);

module.exports = mongoose.model("MessageHistory", messageHistorySchema);
