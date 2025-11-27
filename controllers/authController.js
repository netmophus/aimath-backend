const User = require("../models/userModel");
const StudentProfile = require("../models/studentProfileModel");
const jwt = require("jsonwebtoken");
const { sendSMS } = require("../utils/sendSMS");
const { sendOTPEmail, sendResetPasswordEmail } = require("../utils/sendEmail");
const Otp = require("../models/OtpModel");



const sendResetCode = async (req, res) => {
  const { phone, email } = req.body;

  if (!phone && !email) {
    return res.status(400).json({ message: "Téléphone ou email requis." });
  }

  try {
    let user;
    let formattedPhone = null;
    let formattedEmail = null;

    if (phone) {
      formattedPhone = phone.startsWith("+227") ? phone : `+227${phone.replace(/\D/g, "")}`;
      user = await User.findOne({ phone: formattedPhone });
      if (!user) {
        return res.status(404).json({ message: "Aucun utilisateur avec ce téléphone." });
      }
    } else if (email) {
      formattedEmail = email.toLowerCase().trim();
      user = await User.findOne({ email: formattedEmail });
      if (!user) {
        return res.status(404).json({ message: "Aucun utilisateur avec cet email." });
      }
    }

    const code = Math.floor(1000 + Math.random() * 9000).toString(); // 4 chiffres
    const expiration = new Date(Date.now() + 5 * 60 * 1000); // expire dans 5 min

    // Supprimer les anciens OTP
    if (formattedPhone) {
      await Otp.deleteMany({ phone: formattedPhone });
      await Otp.create({ phone: formattedPhone, otp: code, expiresAt: expiration });
    } else if (formattedEmail) {
      await Otp.deleteMany({ email: formattedEmail });
      await Otp.create({ email: formattedEmail, otp: code, expiresAt: expiration });
    }

    // Envoyer le code par SMS ou email
    if (formattedPhone) {
      const sms = await sendSMS(
        formattedPhone,
        `🔐 Code de réinitialisation Fahimta : ${code}`
      );

      if (!sms.success) {
        return res.status(500).json({ message: "Échec d'envoi du SMS." });
      }

      return res.status(200).json({ message: "✅ Code envoyé par SMS." });
    } else if (formattedEmail) {
      const emailResponse = await sendResetPasswordEmail(formattedEmail, code);

      if (!emailResponse.success) {
        console.error("❌ Erreur envoi email réinitialisation :", emailResponse.error);
        return res.status(500).json({ 
          message: "Échec de l'envoi de l'email. Veuillez vérifier votre adresse email et réessayer." 
        });
      }

      console.log(`📧 Code de réinitialisation envoyé par email à ${formattedEmail} : ${code}`);
      return res.status(200).json({ message: "✅ Code envoyé par email." });
    }
  } catch (error) {
    console.error("❌ Erreur sendResetCode :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};








const resetPassword = async (req, res) => {
  const { phone, email, otp, newPassword, confirmPassword } = req.body;

  if ((!phone && !email) || !otp || !newPassword || !confirmPassword) {
    return res.status(400).json({ message: "Téléphone ou email, OTP et deux mots de passe sont requis." });
  }
  if (newPassword !== confirmPassword) {
    return res.status(400).json({ message: "Les mots de passe ne correspondent pas." });
  }

  try {
    let otpEntry;
    let user;
    let formattedPhone = null;
    let formattedEmail = null;

    if (phone) {
      const formatPhone = (input) => {
        const digits = String(input).replace(/\D/g, "");
        return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
      };
      formattedPhone = formatPhone(phone);
      otpEntry = await Otp.findOne({ phone: formattedPhone, otp });
      user = await User.findOne({ phone: formattedPhone });
    } else if (email) {
      formattedEmail = email.toLowerCase().trim();
      otpEntry = await Otp.findOne({ email: formattedEmail, otp });
      user = await User.findOne({ email: formattedEmail });
    }

    if (!otpEntry) {
      return res.status(400).json({ message: "Code invalide ou expiré." });
    }

    if (otpEntry.expiresAt && otpEntry.expiresAt < new Date()) {
      await Otp.deleteOne({ _id: otpEntry._id });
      return res.status(400).json({ message: "Code expiré. Demandez un nouveau code." });
    }

    if (!user) {
      return res.status(404).json({ message: "Utilisateur non trouvé." });
    }

    user.provider = 'local';              // force le hook de hash
    user.password = newPassword;
    user.passwordConfirm = newPassword;   // <-- FIX: aligne avec la validation du modèle
    await user.save();

    // Supprimer les OTP utilisés
    if (formattedPhone) {
      await Otp.deleteMany({ phone: formattedPhone });
    } else if (formattedEmail) {
      await Otp.deleteMany({ email: formattedEmail });
    }

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

// 🔁 Renvoyer l'OTP
const resendOtp = async (req, res) => {
  const { phone, email } = req.body;

  try {
    let user;
    
    if (phone) {
      const formatPhone = (input) => {
        const digits = input.replace(/\D/g, "");
        return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
      };
      const formattedPhone = formatPhone(phone);
      user = await User.findOne({ phone: formattedPhone });
    } else if (email) {
      user = await User.findOne({ email: email.toLowerCase().trim() });
    } else {
      return res.status(400).json({ message: "Téléphone ou email requis." });
    }

    if (!user) {
      return res.status(404).json({ message: "Utilisateur introuvable." });
    }

    if (user.isVerified) {
      return res.status(400).json({ message: "Utilisateur déjà vérifié." });
    }

    // Générer un nouveau code OTP
    const otp = generateOTP();
    user.otp = otp;
    await user.save();

    // Envoyer le SMS ou email selon la méthode
    if (phone) {
      const formatPhone = (input) => {
        const digits = input.replace(/\D/g, "");
        return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
      };
      const formattedPhone = formatPhone(phone);
      const smsResponse = await sendSMS(
        formattedPhone,
        `Votre code de vérification est : ${otp}`
      );

      console.log(`🔕 OTP renvoyé pour ${formattedPhone} : ${otp}`);

      if (!smsResponse.success) {
        return res.status(500).json({ message: "Échec de l'envoi du SMS." });
      }

      return res.status(200).json({ message: "✅ Un nouveau code a été envoyé par SMS." });
    } else if (email) {
      const emailResponse = await sendOTPEmail(email.toLowerCase().trim(), otp);
      
      if (!emailResponse.success) {
        console.error("❌ Erreur envoi email OTP :", emailResponse.error);
        return res.status(500).json({ 
          message: "Échec de l'envoi de l'email. Veuillez vérifier votre adresse email et réessayer." 
        });
      }
      
      console.log(`📧 OTP renvoyé par email à ${email} : ${otp}`);
      return res.status(200).json({ message: "✅ Un nouveau code a été envoyé par email." });
    }
  } catch (error) {
    console.error("❌ Erreur lors du renvoi de l'OTP :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};



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

    // 🔐 Inscription classique → vérifier téléphone OU email + mot de passe + confirmation
    if ((!formattedPhone && !email) || !password || !confirmPassword) {
      return res.status(400).json({
        message: "Téléphone ou email, mot de passe et confirmation requis pour l'inscription classique.",
      });
    }

    if (password !== confirmPassword) {
      return res.status(400).json({ message: "Les mots de passe ne correspondent pas." });
    }

    // 📩 Génération OTP
    const otp = generateOTP();
    
    // Envoi OTP par SMS si téléphone, sinon par email
    if (formattedPhone) {
      const smsResponse = await sendSMS(
        formattedPhone,
        `Votre code de vérification est : ${otp}`
      );

      // (en dev) log de l'OTP simulé
      console.log(`🔕 Envoi de SMS désactivé. OTP simulé pour ${formattedPhone} : ${otp}`);

      if (!smsResponse.success) {
        return res.status(500).json({ message: "Échec de l'envoi du SMS. Veuillez réessayer." });
      }
    } else if (email) {
      const emailResponse = await sendOTPEmail(email.toLowerCase().trim(), otp);
      
      if (!emailResponse.success) {
        console.error("❌ Erreur envoi email OTP :", emailResponse.error);
        return res.status(500).json({ 
          message: "Échec de l'envoi de l'email. Veuillez vérifier votre adresse email et réessayer." 
        });
      }
      
      console.log(`📧 OTP envoyé par email à ${email} : ${otp}`);
    }

    // ⚙️ Crée l'utilisateur (utilise la virtual passwordConfirm du modèle)
    const userData = {
      password,
      fullName,
      schoolName,
      city,
      role,
      otp,
      isVerified: false,
    };

    if (formattedPhone) {
      userData.phone = formattedPhone;
    }
    if (email) {
      userData.email = email.toLowerCase().trim();
    }

    const user = new User(userData);
    user.passwordConfirm = confirmPassword; // ✅ passe la confirmation au modèle (pre('validate'))

    await user.save();

    return res.status(201).json({
      message: formattedPhone 
        ? "✅ Utilisateur enregistré. Veuillez vérifier votre téléphone."
        : "✅ Utilisateur enregistré. Veuillez vérifier votre email.",
      phone: user.phone,
      email: user.email,
    });
  } catch (error) {
    console.error("❌ Erreur lors de l'inscription :", error);
    res.status(500).json({ message: "Erreur serveur lors de l'inscription." });
  }
};


const verifyOTP = async (req, res) => {
  const { phone, email, otp } = req.body;

  try {
    let user;
    
    if (phone) {
      const formatPhone = (input) => {
        const digits = input.replace(/\D/g, "");
        return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
      };
      const formattedPhone = formatPhone(phone);
      user = await User.findOne({ phone: formattedPhone });
    } else if (email) {
      user = await User.findOne({ email: email.toLowerCase().trim() });
    } else {
      return res.status(400).json({ message: "Téléphone ou email requis." });
    }

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
    console.error("❌ Erreur lors de la vérification :", error);
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

user.lastLoginAt = new Date();
user.loginCount = (user.loginCount || 0) + 1;
await user.save({ validateBeforeSave: false });



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


      // ➕ AJOUTE ICI (avant le return)
    user.lastLoginAt = new Date();
    user.loginCount = (user.loginCount || 0) + 1;
    await user.save({ validateBeforeSave: false });

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
    companyName: user.companyName,
    region: user.region,
    commissionDefaultCfa: user.commissionDefaultCfa,
    isVerified: user.isVerified,
    isSubscribed, // ← calculé ici
    subscriptionStart: user.subscriptionStart,
    subscriptionEnd: user.subscriptionEnd,
    createdAt: user.createdAt,
    lastLoginAt: user.lastLoginAt,
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


module.exports = { registerUser, loginUser , verifyOTP, getMe, sendResetCode, resetPassword, resendOtp };
