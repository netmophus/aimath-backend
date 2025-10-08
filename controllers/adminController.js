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




// 📄 Liste paginée + recherche avancée + tri + filtres
const getAllUsers = async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 10;
    const search = req.query.search || ""; // Recherche multi-critères
    const role = req.query.role || ""; // Filtre par rôle
    const status = req.query.status || ""; // Filtre par statut (active/inactive)
    const subscription = req.query.subscription || ""; // Filtre par abonnement (subscribed/not-subscribed)
    const sortBy = req.query.sortBy || "createdAt"; // Colonne de tri
    const sortOrder = req.query.sortOrder === "asc" ? 1 : -1; // Ordre de tri

    // ✅ Construction de la query avec filtres multiples
    const query = {};

    // Recherche multi-critères (nom, téléphone, email, école)
    if (search) {
      query.$or = [
        { fullName: { $regex: search, $options: "i" } },
        { phone: { $regex: search, $options: "i" } },
        { email: { $regex: search, $options: "i" } },
        { schoolName: { $regex: search, $options: "i" } },
      ];
    }

    // Filtre par rôle
    if (role) {
      query.role = role;
    }

    // Filtre par statut actif/inactif
    if (status === "active") {
      query.isActive = true;
    } else if (status === "inactive") {
      query.isActive = false;
    }

    // Filtre par abonnement
    if (subscription === "subscribed") {
      query.isSubscribed = true;
    } else if (subscription === "not-subscribed") {
      query.isSubscribed = false;
    }

    // ✅ Récupération avec tri et pagination
    const totalUsers = await User.countDocuments(query);
    const users = await User.find(query)
      .sort({ [sortBy]: sortOrder })
      .skip((page - 1) * limit)
      .limit(limit)
      .select("-password -otp -__v");

    // ✅ Statistiques globales
    const stats = {
      total: await User.countDocuments(),
      active: await User.countDocuments({ isActive: true }),
      inactive: await User.countDocuments({ isActive: false }),
      students: await User.countDocuments({ role: "student" }),
      teachers: await User.countDocuments({ role: "teacher" }),
      subscribed: await User.countDocuments({ isSubscribed: true }),
      notSubscribed: await User.countDocuments({ isSubscribed: false }),
    };

    res.status(200).json({
      users,
      totalUsers,
      totalPages: Math.ceil(totalUsers / limit),
      currentPage: page,
      stats, // ✅ Stats pour le dashboard
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



// 📊 Export CSV des utilisateurs
const exportUsersCSV = async (req, res) => {
  try {
    const { role, status, subscription } = req.query;

    // Construction de la query (mêmes filtres que getAllUsers)
    const query = {};
    if (role) query.role = role;
    if (status === "active") query.isActive = true;
    else if (status === "inactive") query.isActive = false;
    if (subscription === "subscribed") query.isSubscribed = true;
    else if (subscription === "not-subscribed") query.isSubscribed = false;

    const users = await User.find(query)
      .sort({ createdAt: -1 })
      .select("-password -otp -__v");

    // ✅ Génération CSV
    let csv = "Nom,Téléphone,Email,École,Rôle,Statut,Abonnement,Date d'inscription\n";
    
    users.forEach((user) => {
      csv += `"${user.fullName || ""}","${user.phone || ""}","${user.email || ""}","${user.schoolName || ""}","${user.role}","${user.isActive ? "Actif" : "Inactif"}","${user.isSubscribed ? "Oui" : "Non"}","${new Date(user.createdAt).toLocaleDateString("fr-FR")}"\n`;
    });

    res.setHeader("Content-Type", "text/csv; charset=utf-8");
    res.setHeader("Content-Disposition", `attachment; filename="users_${Date.now()}.csv"`);
    res.status(200).send("\uFEFF" + csv); // BOM UTF-8 pour Excel
  } catch (err) {
    console.error("Erreur export CSV :", err);
    res.status(500).json({ message: "Erreur lors de l'export" });
  }
};

// 🔄 Actions groupées (activation/désactivation multiple)
const bulkActionUsers = async (req, res) => {
  try {
    const { userIds, action } = req.body; // action: "activate" | "deactivate"

    if (!Array.isArray(userIds) || userIds.length === 0) {
      return res.status(400).json({ message: "Liste d'utilisateurs vide" });
    }

    if (!["activate", "deactivate"].includes(action)) {
      return res.status(400).json({ message: "Action invalide" });
    }

    // ✅ Empêcher la désactivation des admins
    const admins = await User.find({ _id: { $in: userIds }, role: "admin" });
    if (admins.length > 0 && action === "deactivate") {
      return res.status(403).json({ message: "Impossible de désactiver un administrateur" });
    }

    const isActive = action === "activate";
    const result = await User.updateMany(
      { _id: { $in: userIds }, role: { $ne: "admin" } }, // Exclure les admins
      { $set: { isActive } }
    );

    res.status(200).json({
      message: `${result.modifiedCount} utilisateur(s) ${isActive ? "activé(s)" : "désactivé(s)"}`,
      modifiedCount: result.modifiedCount,
    });
  } catch (err) {
    console.error("Erreur actions groupées :", err);
    res.status(500).json({ message: "Erreur serveur" });
  }
};

// 🔍 Détails complets d'un utilisateur
const getUserDetails = async (req, res) => {
  try {
    const user = await User.findById(req.params.id).select("-password -otp");

    if (!user) {
      return res.status(404).json({ message: "Utilisateur non trouvé" });
    }

    // ✅ Informations supplémentaires (historique, stats, etc.)
    const details = {
      user,
      subscriptionHistory: [], // TODO: Ajouter historique des abonnements si besoin
      activityLog: [], // TODO: Ajouter logs d'activité si besoin
      stats: {
        joinedDaysAgo: Math.floor((Date.now() - new Date(user.createdAt)) / (1000 * 60 * 60 * 24)),
        lastLoginDaysAgo: user.lastLogin ? Math.floor((Date.now() - new Date(user.lastLogin)) / (1000 * 60 * 60 * 24)) : null,
      },
    };

    res.status(200).json(details);
  } catch (err) {
    console.error("Erreur détails utilisateur :", err);
    res.status(500).json({ message: "Erreur serveur" });
  }
};

module.exports = { 
  createAdmin, 
  createRechargeCode, 
  getAllUsers, 
  toggleUserStatus, 
  getAdminStats,
  exportUsersCSV, // ✅ Nouveau
  bulkActionUsers, // ✅ Nouveau
  getUserDetails, // ✅ Nouveau
};

