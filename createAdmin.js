// createAdmin.js
const mongoose = require("mongoose");
const bcrypt = require("bcryptjs");
const User = require("./models/userModel"); // ajuste le chemin selon ton projet

const MONGO_URI = process.env.MONGO_URI || "mongodb://127.0.0.1:27017/aimathsdb"; // adapte l'URL si besoin

const createAdmin = async () => {
  try {
    await mongoose.connect(MONGO_URI);
    console.log("✅ Connecté à MongoDB");

    const phone = "+22780648383";
    const plainPassword = "123456";

    const existing = await User.findOne({ phone });
    if (existing) {
      console.log("❌ Un utilisateur avec ce numéro existe déjà.");
      return process.exit(1);
    }

    // const hashedPassword = await bcrypt.hash(plainPassword, 10);

    const admin = new User({
      phone,
      password: plainPassword,
      role: "admin",
      isVerified: true,
    });

    await admin.save();
    console.log("✅ Administrateur créé avec succès.");
    process.exit(0);
  } catch (err) {
    console.error("❌ Erreur :", err.message);
    process.exit(1);
  }
};

createAdmin();
