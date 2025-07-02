const User = require("../models/userModel");
const StudentProfile = require("../models/studentProfileModel");
const jwt = require("jsonwebtoken");
const { sendSMS } = require("../utils/sendSMS");


// 🔐 Générer token JWT
const generateToken = (id) => {
  return jwt.sign({ id }, process.env.JWT_SECRET, { expiresIn: "7d" });
};

// 🔐 INSCRIPTION

const generateOTP = () => Math.floor(1000 + Math.random() * 9000).toString(); // 4 chiffres



// const registerUser = async (req, res) => {
//   const { phone, password, classLevel, role = "eleve" } = req.body;

//   const formatPhone = (input) => {
//     const digits = input.replace(/\D/g, "");
//     return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
//   };

//   const formattedPhone = formatPhone(phone);

//   try {
//     const existingUser = await User.findOne({ phone: formattedPhone });
//     if (existingUser) {
//       return res.status(400).json({ message: "Ce numéro est déjà utilisé." });
//     }

//     // ⚠️ Si c’est un élève, on vérifie que classLevel est fourni
//     if (role === "eleve" && !classLevel) {
//       return res.status(400).json({ message: "Le niveau scolaire (classLevel) est requis." });
//     }

//     const otp = generateOTP();

//     const smsResponse = await sendSMS(formattedPhone, `Votre code de vérification est : ${otp}`);
//     if (!smsResponse.success) {
//       return res.status(500).json({ message: "Échec de l'envoi du SMS. Veuillez réessayer." });
//     }

//     const newUserData = {
//       phone: formattedPhone,
//       password,
//       otp,
//       isVerified: false,
//       role,
//     };

//     if (role === "eleve") {
//       newUserData.classLevel = classLevel;
//     }

//     const user = await User.create(newUserData);

//     res.status(201).json({
//       message: "✅ Utilisateur enregistré. Veuillez vérifier votre téléphone.",
//       phone: user.phone,
//     });
//   } catch (error) {
//     console.error(error);
//     res.status(500).json({ message: "Erreur lors de l'inscription." });
//   }
// };

const registerUser = async (req, res) => {
  const { phone, password, fullName, schoolName, city, role = "eleve" } = req.body;

  const formatPhone = (input) => {
    const digits = input.replace(/\D/g, "");
    return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
  };

  const formattedPhone = formatPhone(phone);

  try {
    const existingUser = await User.findOne({ phone: formattedPhone });
    if (existingUser) {
      return res.status(400).json({ message: "Ce numéro est déjà utilisé." });
    }

    // ✅ Vérification des champs obligatoires
    if (!fullName || !schoolName || !city) {
      return res.status(400).json({ message: "Tous les champs sont requis (nom, école, ville)." });
    }

    const otp = generateOTP();

    const smsResponse = await sendSMS(
      formattedPhone,
      `Votre code de vérification est : ${otp}`
    );

    if (!smsResponse.success) {
      return res.status(500).json({ message: "Échec de l'envoi du SMS. Veuillez réessayer." });
    }

    const newUserData = {
      phone: formattedPhone,
      password,
      otp,
      isVerified: false,
      role,
      fullName,
      schoolName,
      city,
    };

    const user = await User.create(newUserData);

    res.status(201).json({
      message: "✅ Utilisateur enregistré. Veuillez vérifier votre téléphone.",
      phone: user.phone,
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: "Erreur lors de l'inscription." });
  }
};



const verifyOTP = async (req, res) => {
  const { phone, otp } = req.body;

  const formatPhone = (input) => {
    const digits = input.replace(/\D/g, "");
    return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
  };

  const formattedPhone = formatPhone(phone);

  try {
    const user = await User.findOne({ phone: formattedPhone });

    if (!user) {
      return res.status(404).json({ message: "Utilisateur introuvable." });
    }

    if (user.isVerified) {
      return res.status(400).json({ message: "Utilisateur déjà vérifié." });
    }

    if (user.otp !== otp) {
      return res.status(400).json({ message: "Code incorrect." });
    }

    user.isVerified = true;
    user.otp = null;
    await user.save();

    res.status(200).json({
      message: "✅ Vérification réussie.",
      token: generateToken(user._id),
    });
  } catch (error) {
    res.status(500).json({ message: "Erreur lors de la vérification." });
  }
};


  
// 🔐 CONNEXION



const loginUser = async (req, res) => {
  const { phone, password } = req.body;

  const formatPhone = (input) => {
    const digits = input.replace(/\D/g, "");
    return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
  };

  const formattedPhone = formatPhone(phone);

  console.log("🔐 Tentative de connexion pour :", formattedPhone);

  try {
    const user = await User.findOne({ phone: formattedPhone });

    if (!user) {
      console.log("❌ Utilisateur non trouvé.");
      return res.status(401).json({ message: "Téléphone ou mot de passe invalide." });
    }

    const isMatch = await user.matchPassword(password);

    if (!isMatch) {
      console.log("❌ Mot de passe incorrect.");
      return res.status(401).json({ message: "Téléphone ou mot de passe invalide." });
    }

    console.log("✅ Connexion réussie pour :", user.fullName || user.phone);

    const responseData = {
      _id: user._id,
      phone: user.phone,
      role: user.role,
      token: generateToken(user._id),
      isSubscribed: user.isSubscribed || false,
      fullName: user.fullName,
      schoolName: user.schoolName,
      city: user.city,
    };

    res.json(responseData);
  } catch (error) {
    console.error("💥 Erreur lors de la connexion :", error);
    res.status(500).json({ message: "Erreur lors de la connexion." });
  }
};


//   const getMe = async (req, res) => {
//     const user = req.user;
  
//     let studentProfile = null;
  
//     if (user.role === "eleve") {
//       studentProfile = await StudentProfile.findOne({ user: user._id });
//     }
  
//     // ✅ Log côté serveur
//     console.log("📦 /auth/me → Données retournées :", {
//       _id: user._id,
//       phone: user.phone,
//       role: user.role,
//       isVerified: user.isVerified,
//       ...(studentProfile && {
//         isActive: studentProfile.isActive,
//         balance: studentProfile.balance,
//         subscriptionExpiresAt: studentProfile.subscriptionExpiresAt,
//         dailyUsage: studentProfile.dailyUsage || 0,
//       }),
//     });
  
  


//     res.json({
//   _id: user._id,
//   phone: user.phone,
//   role: user.role,
//   isVerified: user.isVerified,
//   classLevel: user.classLevel, // ✅ ajoute cette ligne
//   ...(studentProfile && {
//     isActive: studentProfile.isActive,
//     balance: studentProfile.balance,
//     subscriptionExpiresAt: studentProfile.subscriptionExpiresAt,
//     dailyUsage: studentProfile.dailyUsage || 0,
//   }),




// });

//   };



// const getMe = async (req, res) => {
//   try {
//     const user = await User.findById(req.user.id).select(
//       "_id phone role isVerified fullName isSubscribed subscriptionStart subscriptionEnd schoolName city"
//     );

//     if (!user) return res.status(404).json({ message: "Utilisateur non trouvé" });

//     res.json(user);
//   } catch (err) {
//     console.error("❌ Erreur dans /auth/me :", err.message);
//     res.status(500).json({ message: "Erreur serveur" });
//   }
// };

  

const getMe = async (req, res) => {
  const user = req.user;

  let studentProfile = null;

  if (user.role === "eleve") {
    studentProfile = await StudentProfile.findOne({ user: user._id });
  }

  // ✅ Log serveur
  console.log("📦 /auth/me → Données retournées :", {
    _id: user._id,
    phone: user.phone,
    role: user.role,
    isVerified: user.isVerified,
    isSubscribed: user.isSubscribed, // 👈 ajouté ici
    subscriptionStart: user.subscriptionStart,
    subscriptionEnd: user.subscriptionEnd,
    ...(studentProfile && {
      isActive: studentProfile.isActive,
      balance: studentProfile.balance,
      subscriptionExpiresAt: studentProfile.subscriptionExpiresAt,
      dailyUsage: studentProfile.dailyUsage || 0,
    }),
  });

  // ✅ Réponse envoyée au frontend
  res.json({
    _id: user._id,
    phone: user.phone,
    role: user.role,
    isVerified: user.isVerified,
    classLevel: user.classLevel,
    isSubscribed: user.isSubscribed, // 👈 ici aussi
    subscriptionStart: user.subscriptionStart,
    subscriptionEnd: user.subscriptionEnd,
    ...(studentProfile && {
      isActive: studentProfile.isActive,
      balance: studentProfile.balance,
      subscriptionExpiresAt: studentProfile.subscriptionExpiresAt,
      dailyUsage: studentProfile.dailyUsage || 0,
    }),
  });
};

  
module.exports = { registerUser, loginUser , verifyOTP, getMe};
