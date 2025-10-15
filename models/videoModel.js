
const mongoose = require("mongoose");

const videoSchema = new mongoose.Schema(
  {
    title: { type: String, required: true, trim: true },
    description: { type: String, required: true },
    level: { type: String, required: true },
    subject: {
      type: String,
      enum: ["maths", "physique", "chimie", "svt"],
      default: "maths",
    },
    badge: {
      type: String,
      enum: ["gratuit", "prenuim"],
      default: "gratuit",
    },
    videoUrl: { type: String, required: true },
    thumbnail: { type: String },
    viewCount: { type: Number, default: 0 },
    videosSupplementaires: [
      {
        title: { type: String },
        videoUrl: { type: String, required: true },
        thumbnail: { type: String },
      }
    ],
  },
  { timestamps: true }
);

module.exports = mongoose.model("Video", videoSchema);
