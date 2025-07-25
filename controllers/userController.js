const User = require("../models/userModel");

// ➕ Créer un enseignant
const createTeacher = async (req, res) => {
  try {
    const { fullName, phone, email, schoolName, city, password } = req.body;

    const existingUser = await User.findOne({ phone });
    if (existingUser) return res.status(400).json({ message: "Ce téléphone est déjà utilisé." });

    const newTeacher = new User({
      fullName,
      phone,
      email,
      schoolName,
      city,
      password,
      role: "teacher",
      isVerified: true,
    });

    await newTeacher.save();
    res.status(201).json({ message: "Enseignant créé avec succès." });
  } catch (error) {
    console.error("Erreur création enseignant:", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// 📄 Liste de tous les enseignants
const getAllTeachers = async (req, res) => {
  try {
    const teachers = await User.find({ role: "teacher" }).select("-password");
    res.json(teachers);
  } catch (error) {
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// ✏️ Modifier un enseignant
const updateTeacher = async (req, res) => {
  try {
    const { id } = req.params;
    const updates = req.body;
    const teacher = await User.findByIdAndUpdate(id, updates, { new: true });
    res.json(teacher);
  } catch (error) {
    res.status(500).json({ message: "Erreur lors de la mise à jour." });
  }
};

// ❌ Supprimer un enseignant
const deleteTeacher = async (req, res) => {
  try {
    const { id } = req.params;
    await User.findByIdAndDelete(id);
    res.json({ message: "Enseignant supprimé avec succès." });
  } catch (error) {
    res.status(500).json({ message: "Erreur lors de la suppression." });
  }
};

// ✅ Activer/Désactiver
const toggleTeacherStatus = async (req, res) => {
  try {
    const { id } = req.params;
    const teacher = await User.findById(id);
    teacher.isActive = !teacher.isActive;
    await teacher.save();
    res.json({ message: `Compte ${teacher.isActive ? "activé" : "désactivé"} avec succès.` });
  } catch (error) {
    res.status(500).json({ message: "Erreur lors du changement de statut." });
  }
};

module.exports = {
  createTeacher,
  getAllTeachers,
  updateTeacher,
  deleteTeacher,
  toggleTeacherStatus,
};
