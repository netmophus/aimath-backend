const StudentProfile = require("../models/studentProfileModel");

// ➕ Créer ou mettre à jour le profil élève
const createOrUpdateStudentProfile = async (req, res) => {
  const { fullName, level, classe } = req.body;
  const userId = req.user._id; // grâce à authMiddleware

  try {
    let profile = await StudentProfile.findOne({ user: userId });

    if (profile) {
      // Mise à jour si le profil existe déjà
      profile.fullName = fullName;
      profile.level = level;
      profile.classe = classe;
      await profile.save();
    } else {
      // Création si c’est la première fois
      profile = await StudentProfile.create({
        user: userId,
        fullName,
        level,
        classe,
      });
    }

    res.status(200).json({
      message: "Profil élève enregistré avec succès",
      profile,
    });
  } catch (error) {
    res.status(500).json({ message: "Erreur lors de l'enregistrement du profil." });
  }
};

module.exports = { createOrUpdateStudentProfile };
