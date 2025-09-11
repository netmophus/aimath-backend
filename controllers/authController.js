const User = require("../models/userModel");
const StudentProfile = require("../models/studentProfileModel");
const jwt = require("jsonwebtoken");
const { sendSMS } = require("../utils/sendSMS");
const Otp = require("../models/OtpModel");



const sendResetCode = async (req, res) => {
  const { phone } = req.body;

  if (!phone) return res.status(400).json({ message: "Téléphone requis." });

  const formattedPhone = phone.startsWith("+227") ? phone : `+227${phone.replace(/\D/g, "")}`;

  try {
    const user = await User.findOne({ phone: formattedPhone });
    if (!user) {
      return res.status(404).json({ message: "Aucun utilisateur avec ce téléphone." });
    }

    const code = Math.floor(1000 + Math.random() * 9000).toString(); // 4 chiffres
    const expiration = new Date(Date.now() + 5 * 60 * 1000); // expire dans 5 min

    await Otp.deleteMany({ phone: formattedPhone }); // Supprimer les anciens OTP
   await Otp.create({ phone: formattedPhone, otp: code, expiresAt: expiration });


    const sms = await sendSMS(
      formattedPhone,
      `🔐 Code de réinitialisation Fahimta : ${code}`
    );

    if (!sms.success) {
      return res.status(500).json({ message: "Échec d'envoi du SMS." });
    }

    return res.status(200).json({ message: "✅ Code envoyé par SMS." });
  } catch (error) {
    console.error("❌ Erreur sendResetCode :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};








const resetPassword = async (req, res) => {
  const { phone, otp, newPassword, confirmPassword } = req.body;

  if (!phone || !otp || !newPassword || !confirmPassword) {
    return res.status(400).json({ message: "Téléphone, OTP et deux mots de passe sont requis." });
  }
  if (newPassword !== confirmPassword) {
    return res.status(400).json({ message: "Les mots de passe ne correspondent pas." });
  }

  const formatPhone = (input) => {
    const digits = String(input).replace(/\D/g, "");
    return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
  };
  const formattedPhone = formatPhone(phone);

  try {
    const otpEntry = await Otp.findOne({ phone: formattedPhone, otp });
    if (!otpEntry) return res.status(400).json({ message: "Code invalide ou expiré." });
    if (otpEntry.expiresAt && otpEntry.expiresAt < new Date()) {
      await Otp.deleteOne({ _id: otpEntry._id });
      return res.status(400).json({ message: "Code expiré. Demandez un nouveau code." });
    }

    const user = await User.findOne({ phone: formattedPhone });
    if (!user) return res.status(404).json({ message: "Utilisateur non trouvé." });

    user.provider = 'local';              // force le hook de hash
    user.password = newPassword;
    user.passwordConfirm = newPassword;   // <-- FIX: aligne avec la validation du modèle
    await user.save();

    await Otp.deleteMany({ phone: formattedPhone });
    return res.json({ message: "✅ Mot de passe réinitialisé avec succès." });
  } catch (err) {
    console.error("❌ Erreur resetPassword :", err);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};







const generateToken = (id) => {
  return jwt.sign({ id }, process.env.JWT_SECRET, { expiresIn: "7d" });
};

// 🔐 INSCRIPTION

const generateOTP = () => Math.floor(1000 + Math.random() * 9000).toString(); // 4 chiffres



const registerUser = async (req, res) => {
  const {
    phone,
    email,
    password,
    confirmPassword,      // ✅ ajouté
    fullName,
    schoolName,
    city,
    role = "eleve",
    provider,             // "google" ou "facebook"
    providerId,           // ID renvoyé par Google/Facebook
  } = req.body;

  // 🔧 Formate le téléphone si présent
  const formatPhone = (input) => {
    const digits = input.replace(/\D/g, "");
    return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
  };
  const formattedPhone = phone ? formatPhone(phone) : null;

  try {
    // 🔍 Vérifie s'il existe déjà un utilisateur (téléphone ou email ou providerId)
    const existingUser = await User.findOne({
      $or: [
        formattedPhone ? { phone: formattedPhone } : null,
        email ? { email } : null,
        providerId ? { providerId } : null,
      ].filter(Boolean),
    });

    if (existingUser) {
      return res.status(400).json({ message: "Un compte existe déjà avec ces identifiants." });
    }

    // ✅ Vérifie les champs communs
    if (!fullName || !schoolName || !city) {
      return res.status(400).json({ message: "Nom, école et ville sont obligatoires." });
    }

    // 🧩 Inscription via Google/Facebook (pas de mot de passe requis)
    if (provider && providerId) {
      const newUser = await User.create({
        email,
        fullName,
        schoolName,
        city,
        role,
        provider,
        providerId,
        isVerified: true,
      });

      return res.status(201).json({
        message: "✅ Compte Google/Facebook créé avec succès.",
        token: generateToken(newUser._id),
      });
    }

    // 🔐 Inscription classique → vérifier téléphone + mot de passe + confirmation
    if (!formattedPhone || !password || !confirmPassword) {
      return res.status(400).json({
        message: "Téléphone, mot de passe et confirmation requis pour l'inscription classique.",
      });
    }

    if (password !== confirmPassword) {
      return res.status(400).json({ message: "Les mots de passe ne correspondent pas." });
    }

    // 📩 Envoi OTP par SMS
    const otp = generateOTP();
    const smsResponse = await sendSMS(
      formattedPhone,
      `Votre code de vérification est : ${otp}`
    );

    // (en dev) log de l’OTP simulé
    console.log(`🔕 Envoi de SMS désactivé. OTP simulé pour ${formattedPhone} : ${otp}`);

    if (!smsResponse.success) {
      return res.status(500).json({ message: "Échec de l'envoi du SMS. Veuillez réessayer." });
    }

    // ⚙️ Crée l'utilisateur (utilise la virtual passwordConfirm du modèle)
    const user = new User({
      phone: formattedPhone,
      email,
      password,
      fullName,
      schoolName,
      city,
      role,
      otp,
      isVerified: false,
    });
    user.passwordConfirm = confirmPassword; // ✅ passe la confirmation au modèle (pre('validate'))

    await user.save();

    return res.status(201).json({
      message: "✅ Utilisateur enregistré. Veuillez vérifier votre téléphone.",
      phone: user.phone,
    });
  } catch (error) {
    console.error("❌ Erreur lors de l'inscription :", error);
    res.status(500).json({ message: "Erreur serveur lors de l'inscription." });
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
  const { phone, email, password, provider, providerId, fullName } = req.body;

  try {
    // ✅ Connexion via Google
   if (provider === "google" && providerId && email) {
  let user = await User.findOne({ email });

  if (!user) {
    user = await User.create({
      email,
      provider,
      providerId,
      fullName: fullName || "Utilisateur Google",
      schoolName: "École non précisée",   // ← ajouté
      city: "Ville non précisée",         // ← ajouté
      role: "eleve",
      isVerified: true,
       
    });
  }


      return res.json({
        _id: user._id,
        email: user.email,
        fullName: user.fullName,
        role: user.role,
        token: generateToken(user._id),
        profileCompleted: user.profileCompleted,
      });
    }

    // ✅ Connexion classique par téléphone ou email
    if ((phone || email) && password) {
      const query = phone
        ? { phone: phone.startsWith("+") ? phone : `+227${phone}` }
        : { email };

      const user = await User.findOne(query);

      if (!user) {
        return res.status(401).json({ message: "Identifiants invalides." });
      }

      if (user.isActive === false) {
  return res.status(403).json({ message: "Votre compte a été désactivé." });
}

      const isMatch = await user.matchPassword(password);
      if (!isMatch) {
        return res.status(401).json({ message: "Mot de passe incorrect." });
      }

      return res.json({
        _id: user._id,
        phone: user.phone,
        email: user.email,
        fullName: user.fullName,
        role: user.role,
        isSubscribed: user.isSubscribed, // ✅ très important
        token: generateToken(user._id),
         profileCompleted: user.profileCompleted,
      });
    }

    // ❌ Cas non pris en charge
    return res.status(400).json({ message: "Requête invalide." });
  } catch (error) {
    console.error("💥 Erreur lors de la connexion :", error);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};




const getMe = async (req, res) => {
  const user = req.user;

  let studentProfile = null;
  if (user.role === "eleve") {
    studentProfile = await StudentProfile.findOne({ user: user._id });
  }

  // Calcul dynamique de l'abonnement (source de vérité = dates)
  const now = new Date();
  const start = user.subscriptionStart ? new Date(user.subscriptionStart) : null;
  const end   = user.subscriptionEnd ? new Date(user.subscriptionEnd) : null;
  const isSubscribed = Boolean(end && end > now && (!start || now >= start));

  // Log serveur
  console.log("📦 /auth/me → Données retournées :", {
    _id: user._id,
    phone: user.phone,
    role: user.role,
    fullName: user.fullName,
    isVerified: user.isVerified,
    isSubscribed, // ← calculé ici
    subscriptionStart: user.subscriptionStart,
    subscriptionEnd: user.subscriptionEnd,
    ...(studentProfile && {
      isActive: studentProfile.isActive,
      balance: studentProfile.balance,
      subscriptionExpiresAt: studentProfile.subscriptionExpiresAt,
      dailyUsage: studentProfile.dailyUsage || 0,
      level: studentProfile.level,
      classe: studentProfile.classe,
    }),
  });

  // Réponse envoyée au frontend
  res.json({
    _id: user._id,
    phone: user.phone,
    role: user.role,
    fullName: user.fullName,
    email: user.email,
    photo: user.photo,
    schoolName: user.schoolName,
    city: user.city,
    isVerified: user.isVerified,
    isSubscribed, // ← calculé ici
    subscriptionStart: user.subscriptionStart,
    subscriptionEnd: user.subscriptionEnd,
    ...(studentProfile && {
      level: studentProfile.level,
      classe: studentProfile.classe,
      isActive: studentProfile.isActive,
      balance: studentProfile.balance,
      subscriptionExpiresAt: studentProfile.subscriptionExpiresAt,
      dailyUsage: studentProfile.dailyUsage || 0,
    }),
  });
};


module.exports = { registerUser, loginUser , verifyOTP, getMe, sendResetCode, resetPassword };
