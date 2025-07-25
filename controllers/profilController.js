// // controllers/profilController.js
// const User = require('../models/userModel');



// exports.updateProfil = async (req, res) => {
//   try {
//     const userId = req.user._id;
//     const { schoolName, city, level, photo } = req.body;

//     const updatedFields = {};

//     if (schoolName) updatedFields.schoolName = schoolName;
//     if (city) updatedFields.city = city;
//     if (level) updatedFields.level = level;
//     if (photo) updatedFields.photo = photo;

//     // 🔍 Récupère les données actuelles de l'utilisateur pour compléter les champs manquants
//     const userInDb = await User.findById(userId);

//     const finalPhoto = photo || userInDb.photo;
//     const finalSchoolName = schoolName || userInDb.schoolName;
//     const finalCity = city || userInDb.city;
//     const finalLevel = level || userInDb.level;

//     // ✅ Marque le profil comme complet si toutes les infos sont présentes
//     if (finalPhoto && finalSchoolName && finalCity && finalLevel) {
//       updatedFields.profileCompleted = true;
//     }

//     const updatedUser = await User.findByIdAndUpdate(userId, updatedFields, {
//       new: true,
//     });

//     res.status(200).json({
//       message: 'Profil mis à jour avec succès',
//       user: updatedUser,
//     });
//   } catch (error) {
//     console.error('Erreur updateProfil:', error);
//     res.status(500).json({ message: 'Erreur serveur' });
//   }
// };


// exports.getProfil = async (req, res) => {
//   try {
//     const userId = req.user._id;
//     const user = await User.findById(userId).select('-password');

//     if (!user) {
//       return res.status(404).json({ message: 'Utilisateur non trouvé' });
//     }

//     // Mise à jour automatique du champ profileCompleted
//     const isCompleted =
//       user.fullName &&
//       user.schoolName &&
//       user.city &&
//       user.photo;

//     if (user.profileCompleted !== Boolean(isCompleted)) {
//       user.profileCompleted = Boolean(isCompleted);
//       await user.save();
//     }

//     res.status(200).json(user);
//   } catch (error) {
//     console.error('Erreur getProfil:', error);
//     res.status(500).json({ message: 'Erreur serveur' });
//   }
// };
