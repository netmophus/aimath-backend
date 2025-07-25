// const StudentProfile = require("../models/studentProfileModel");

// const iaUsageLimiter = async (req, res, next) => {
//   const userId = req.user._id;

//   try {
//     const student = await StudentProfile.findOne({ user: userId });

//     if (!student) {
//       return res.status(404).json({ message: "Profil élève introuvable." });
//     }

//     const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
//     const lastDate = student.lastUsageDate?.toISOString().slice(0, 10);

//     if (lastDate !== today) {
//       // 🔄 nouveau jour → reset compteur
//       student.dailyUsage = 0;
//       student.lastUsageDate = new Date();
//     }

//     if (student.dailyUsage >= 60) {
//       return res.status(429).json({ message: "❌ Limite journalière atteinte (10 requêtes IA par jour)." });
//     }

//     student.dailyUsage += 1;
//     await student.save();

//     next();
//   } catch (err) {
//     res.status(500).json({ message: "❌ Erreur lors du contrôle d’usage IA." });
//   }
// };

// module.exports = iaUsageLimiter;
