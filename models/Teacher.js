const mongoose = require("mongoose");

const teacherSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    required: true,
    unique: true,
  },

  subjects: {
    type: [String], // Ex: ["Mathématiques", "SVT", "Anglais"]
    required: true,
  },

  levels: {
    type: [String], // Ex: ["Collège - 6ème", "Lycée - Terminale C"]
    required: true,
  },

    level: {
    type: String, // Exemple : "Master en Mathématiques"
    default: "",
  },

    experience: {
    type: String, // Exemple : "7 ans"
    default: "",
  },

gpsLocation: {
  latitude: { type: Number, default: null },
  longitude: { type: Number, default: null },
},


  isAvailable: {
    type: Boolean,
    default: true, // ✅ l’élève pourra savoir si l’enseignant accepte les questions
  },

  createdAt: {
    type: Date,
    default: Date.now,
  },
});

module.exports = mongoose.model("Teacher", teacherSchema);
