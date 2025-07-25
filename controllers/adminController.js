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




// 📄 Liste paginée + recherche
const getAllUsers = async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 10;
    const phone = req.query.phone || "";

    const query = phone ? { phone: { $regex: phone, $options: "i" } } : {};

    const totalUsers = await User.countDocuments(query);
    const users = await User.find(query)
      .sort({ createdAt: -1 })
      .skip((page - 1) * limit)
      .limit(limit)
      .select("-password -otp -__v");

    res.status(200).json({
      users,
      totalUsers,
      totalPages: Math.ceil(totalUsers / limit),
      currentPage: page,
    });
  } catch (err) {
    console.error("Erreur lors de la récupération des utilisateurs :", err);
    res.status(500).json({ message: "Erreur serveur" });
  }
};



const toggleUserStatus = async (req, res) => {
  try {
    const user = await User.findById(req.params.id);

    if (!user) {
      return res.status(404).json({ message: "Utilisateur non trouvé" });
    }

    // 🚫 Interdire la désactivation de l'administrateur
    if (user.role === "admin") {
      return res.status(403).json({ message: "Impossible de désactiver un administrateur." });
    }

    user.isActive = !user.isActive;
    await user.save();

    res.status(200).json({
      message: `Utilisateur ${user.isActive ? "activé" : "désactivé"}`,
      user,
    });
  } catch (err) {
    console.error("Erreur toggle statut utilisateur :", err);
    res.status(500).json({ message: "Erreur serveur" });
  }
};




const getAdminStats = async (req, res) => {
  try {
    const totalTeachers = await User.countDocuments({ role: "teacher" });
    res.json({ totalTeachers });
  } catch (error) {
    console.error("Erreur récupération stats admin:", error);
    res.status(500).json({ message: "Erreur serveur" });
  }
};



module.exports = { createAdmin, createRechargeCode,  getAllUsers,  toggleUserStatus,  getAdminStats };

