

const StudentProfile = require("../models/studentProfileModel");
const User = require("../models/userModel");

// ➕ Créer ou mettre à jour le profil élève + photo + profileCompleted
const createOrUpdateStudentProfile = async (req, res) => {
  const { level, classe, photo } = req.body;
  const userId = req.user._id;

  try {
    let profile = await StudentProfile.findOne({ user: userId });

    if (profile) {
      profile.level = level;
      profile.classe = classe;
      await profile.save();
    } else {
      profile = await StudentProfile.create({
        user: userId,
        level,
        classe,
      });
    }

    // 🔄 Mise à jour du modèle User (photo + profileCompleted)
    await User.findByIdAndUpdate(userId, {
      ...(photo && { photo }),
      profileCompleted: true,
    });

    const user = req.user; // ✅ Correction ici

    res.status(200).json({
      message: "✅ Profil mis à jour avec succès.",
      profile,
      user,
    });
  } catch (error) {
    console.error("❌ Erreur update profil élève :", error);
    res.status(500).json({ message: "Erreur lors de la mise à jour du profil." });
  }
};


module.exports = { createOrUpdateStudentProfile };
