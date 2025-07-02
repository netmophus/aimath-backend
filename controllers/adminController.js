const User = require("../models/userModel");
const RechargeCode = require("../models/rechargeCodeModel");

// ➕ Créer un admin manuellement (à utiliser une fois)
const createAdmin = async (req, res) => {
  const { phone, password } = req.body;

  try {
    const existing = await User.findOne({ phone });
    if (existing) {
      return res.status(400).json({ message: "Ce numéro est déjà utilisé." });
    }

    const user = await User.create({
      phone,
      password,
      role: "admin",
      isVerified: true, // pas d'OTP pour admin
    });

    res.status(201).json({ message: "✅ Administrateur créé.", id: user._id });
  } catch (err) {
    res.status(500).json({ message: "❌ Erreur lors de la création." });
  }
};








// ➕ Créer un code de recharge
const createRechargeCode = async (req, res) => {
  const { code, value, type } = req.body;

  if (!code || !value || !type) {
    return res.status(400).json({ message: "Tous les champs sont requis." });
  }

  try {
    const existing = await RechargeCode.findOne({ code });
    if (existing) {
      return res.status(400).json({ message: "Ce code existe déjà." });
    }

    const newCode = await RechargeCode.create({
      code,
      value,
      type,
    });

    res.status(201).json({ message: "✅ Code de recharge créé avec succès.", code: newCode.code });
  } catch (err) {
    res.status(500).json({ message: "❌ Erreur serveur lors de la création du code." });
  }
};

module.exports = { createAdmin, createRechargeCode };

