


const mongoose = require("mongoose");

const chapterSchema = new mongoose.Schema({
  chapterNumber: {
    type: Number,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  description: String,

  videos: [
    {
      title: { type: String, required: true },
      description: String,
      url: { type: String, required: true },
      image: String, // Facultative
    },
  ],
  pdfs: [
    {
      title: { type: String, required: true },
      description: String,
      url: { type: String, required: true },
      image: String, // Facultative
    },
  ],

  aiEnabled: {
    type: Boolean,
    default: false,
  },

  level: {
    type: String,
    enum: ["college", "lycee"],
    required: true,
  },
  classe: {
    type: String,
    enum: [
      "6ème", "5ème", "4ème", "3ème",
      "Seconde", "Première", "Terminale"
    ],
    required: true,
  },

serie: {
  type: String,
  enum: ["A", "C", "D", "E", "F", "G"], // adapte à tes séries
  required: function () {
    return this.level === "lycee";
  },
},

}, {
  timestamps: true,
});

module.exports = mongoose.model("Chapter", chapterSchema);
