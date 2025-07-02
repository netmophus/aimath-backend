const mongoose = require("mongoose");

const studentProfileSchema = new mongoose.Schema({
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    required: true,
    unique: true,
  },
  fullName: {
    type: String,
    required: true,
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
  balance: {
    type: Number,
    default: 0,
  },
  dailyUsage: {
    type: Number,
    default: 0,
  },
  lastUsageDate: {
    type: Date,
    default: null,
  },
  
  isActive: {
    type: Boolean,
    default: false,
  },
  subscriptionExpiresAt: {
    type: Date,
    default: null,
  },
}, {
  timestamps: true,
});

const StudentProfile = mongoose.model("StudentProfile", studentProfileSchema);
module.exports = StudentProfile;


