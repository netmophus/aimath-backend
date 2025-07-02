

const StudentProfile = require("../models/studentProfileModel");

// Mapping entre classLevel et level + classe
const classLevelMap = {
  "6eme": { level: "college", classe: "6ème" },
  "5eme": { level: "college", classe: "5ème" },
  "4eme": { level: "college", classe: "4ème" },
  "3eme": { level: "college", classe: "3ème" },
  "seconde-a": { level: "lycee", classe: "Seconde" },
  "seconde-c": { level: "lycee", classe: "Seconde" },
  "premiere-a": { level: "lycee", classe: "Première" },
  "premiere-c": { level: "lycee", classe: "Première" },
  "premiere-d": { level: "lycee", classe: "Première" },
  "terminale-a": { level: "lycee", classe: "Terminale" },
  "terminale-c": { level: "lycee", classe: "Terminale" },
  "terminale-d": { level: "lycee", classe: "Terminale" },
};

const createOrUpdateStudentProfile = async (req, res) => {
  const { fullName } = req.body;
  const userId = req.user._id;
  const classLevel = req.user.classLevel;

  try {
    const mapping = classLevelMap[classLevel];

    if (!mapping) {
      return res.status(400).json({ message: "Niveau scolaire inconnu." });
    }

    const { level, classe } = mapping;

    let profile = await StudentProfile.findOne({ user: userId });

    if (profile) {
      profile.fullName = fullName;
      profile.level = level;
      profile.classe = classe;
      await profile.save();
    } else {
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
    res
      .status(500)
      .json({ message: "Erreur lors de l'enregistrement du profil." });
  }
};

module.exports = { createOrUpdateStudentProfile };
