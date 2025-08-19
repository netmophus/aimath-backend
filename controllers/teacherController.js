const SupportRequest = require("../models/SupportRequest");
const User = require("../models/userModel");
const Message = require("../models/Message");
const MessageHistory = require("../models/MessageHistory");

const Teacher = require("../models/Teacher"); // assure-toi que c'est bien importé tout en haut

exports.updateTeacherProfile = async (req, res) => {
  try {
    const teacher = await Teacher.findOne({ userId: req.user._id });
    if (!teacher) {
      return res.status(404).json({ message: "Enseignant non trouvé." });
    }

    const { subjects, levels, level, experience, gpsLocation } = req.body;

    if (subjects) teacher.subjects = subjects;
    if (levels) teacher.levels = levels;
    if (level) teacher.level = level;
    if (experience) teacher.experience = experience;
    if (gpsLocation) teacher.gpsLocation = gpsLocation;

    await teacher.save();

    res.status(200).json({ message: "Profil enseignant mis à jour avec succès." });
  } catch (error) {
    console.error("❌ Erreur mise à jour profil enseignant :", error);
    res.status(500).json({ message: "Erreur serveur lors de la mise à jour." });
  }
};


exports.getSupportRequestsForTeacher = async (req, res) => {
  try {
    const teacherId = req.user._id;

    // Afficher :
    // 1️⃣ Toutes les demandes NON encore attribuées (teacher: null)
    // 2️⃣ Et celles déjà attribuées à CET enseignant
    const requests = await SupportRequest.find({
      $or: [
        { teacher: null },
        { teacher: teacherId }
      ]
    })
      .populate("student", "fullName schoolName city")
      .sort({ createdAt: -1 });

    res.json(requests);
  } catch (error) {
    console.error("❌ Erreur récupération demandes enseignant:", error);
    res.status(500).json({ message: "Erreur serveur lors de la récupération des demandes." });
  }
};





exports.updateSupportRequestStatus = async (req, res) => {
  try {
    const requestId = req.params.id;
    const { status } = req.body;

    const allowedStatuses = ["en_attente", "acceptee", "refusee", "terminee"];
    if (!allowedStatuses.includes(status)) {
      return res.status(400).json({ message: "Statut invalide." });
    }

    const request = await SupportRequest.findById(requestId);

    if (!request) {
      return res.status(404).json({ message: "Demande non trouvée." });
    }

    if (request.status === "terminee") {
      return res.status(403).json({ message: "Cette demande est déjà terminée." });
    }

    // ✅ Attribution de l’enseignant si besoin
    if (!request.teacher) {
      request.teacher = req.user._id;
    } else if (request.teacher.toString() !== req.user._id.toString()) {
      return res.status(403).json({ message: "Cette demande est déjà assignée à un autre enseignant." });
    }

    // ✅ Si le statut devient "terminee", archiver les messages
    if (status === "terminee") {
      const messages = await Message.find({
        $or: [
          { from: request.student, to: request.teacher },
          { from: request.teacher, to: request.student }
        ]
      });

      const historyDocs = messages.map((msg) => ({
        from: msg.from,
        to: msg.to,
        text: msg.text,
        fileUrl: msg.fileUrl,
        fileType: msg.fileType,
        isVoiceMessage: msg.isVoiceMessage,
        read: msg.read,
        createdAt: msg.createdAt,
        originalRequest: request._id,
      }));

      if (historyDocs.length > 0) {
        await MessageHistory.insertMany(historyDocs);
        await Message.deleteMany({
          _id: { $in: messages.map((m) => m._id) }
        });
      }

      request.sessionStarted = false; // Fin de session
    }

    if (status === "acceptee") {
      request.sessionStarted = true;
    }

    request.status = status;
    await request.save();

    // ✅ Populate juste avant envoi
const populatedRequest = await SupportRequest.findById(request._id).populate("student", "fullName schoolName city");

res.status(200).json(populatedRequest);

    // res.status(200).json(request);
  } catch (error) {
    console.error("❌ Erreur mise à jour statut :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};











exports.startSessionForRequest = async (req, res) => {
  try {
    const { id } = req.params;
    const teacherId = req.user._id;

    const request = await SupportRequest.findById(id);

    if (!request) {
      return res.status(404).json({ message: "Demande introuvable." });
    }

    if (request.teacher.toString() !== teacherId.toString()) {
      return res.status(403).json({ message: "Non autorisé." });
    }

    if (request.sessionStarted) {
      return res.status(400).json({ message: "La session a déjà commencé." });
    }

    request.sessionStarted = true;
    await request.save();

    res.json({ message: "Session démarrée avec succès." });
  } catch (error) {
    console.error("❌ Erreur démarrage session :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};



// ✅ Obtenir les infos de l’enseignant connecté
exports.getCurrentTeacher = async (req, res) => {
  try {
    const user = await User.findById(req.user._id).select("fullName _id");
    res.status(200).json(user);
  } catch (error) {
    console.error("❌ Erreur récupération enseignant :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};




// 📸 Mettre à jour la photo de profil
exports.updateTeacherPhoto = async (req, res) => {
  try {
    const user = await User.findById(req.user._id); // pas Teacher
    if (!user) {
      return res.status(404).json({ message: "Utilisateur non trouvé" });
    }

    user.photo = req.body.photo; // Injectée par Cloudinary
    await user.save();

    res.status(200).json({ message: "Photo mise à jour avec succès", photo: user.photo });
  } catch (err) {
    console.error("Erreur mise à jour photo enseignant :", err);
    res.status(500).json({ message: "Erreur serveur" });
  }
};





/* Utilitaire : formatage téléphone -> +227XXXXXXXX */
const formatPhone = (input = "") => {
  const digits = String(input).replace(/\D/g, "");
  if (!digits) return null;
  return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
};

/* ===========================
   ADMIN: liste des enseignants
   GET /api/admin/teachers
=========================== */
exports.adminListTeachers = async (req, res) => {
  try {
    const teachers = await User.find({ role: "teacher" })
      .select("fullName phone schoolName city isActive isVerified profileCompleted photo createdAt")
      .sort({ createdAt: -1 });

    return res.json(teachers);
  } catch (err) {
    console.error("adminListTeachers error:", err);
    return res.status(500).json({ message: "Erreur serveur lors du listing des enseignants." });
  }
};

/* ===========================
   ADMIN: créer un enseignant (sans OTP)
   POST /api/admin/teachers
   body: { fullName, phone, password, schoolName, city }
=========================== */
exports.adminCreateTeacher = async (req, res) => {
  try {
    const { fullName, phone, password, schoolName, city } = req.body;

    if (!fullName || !phone || !password || !schoolName || !city) {
      return res.status(400).json({ message: "Nom, téléphone, mot de passe, école et ville sont obligatoires." });
    }

    const formattedPhone = formatPhone(phone);
    if (!formattedPhone || formattedPhone.length < 12) {
      return res.status(400).json({ message: "Téléphone invalide." });
    }

    const exists = await User.findOne({ phone: formattedPhone });
    if (exists) {
      return res.status(400).json({ message: "Un compte existe déjà avec ce téléphone." });
    }

    // Création SANS OTP
    const user = new User({
      role: "teacher",
      fullName,
      phone: formattedPhone,
      password,
      schoolName,
      city,
      provider: "local",
      isVerified: true,         // pas d’OTP
      isActive: true,
      profileCompleted: false,
    });

    // Le modèle vérifie passwordConfirm en pre('validate'), on le renseigne donc :
    user.passwordConfirm = password;

    await user.save();

    return res.status(201).json({
      message: "✅ Enseignant créé avec succès.",
      teacher: {
        _id: user._id,
        fullName: user.fullName,
        phone: user.phone,
        schoolName: user.schoolName,
        city: user.city,
        isActive: user.isActive,
        isVerified: user.isVerified,
        createdAt: user.createdAt,
      },
    });
  } catch (err) {
    console.error("adminCreateTeacher error:", err);
    return res.status(500).json({ message: "Erreur serveur lors de la création de l'enseignant." });
  }
};

/* ===========================
   ADMIN: activer/désactiver un enseignant
   PATCH /api/admin/teachers/:id/toggle
=========================== */
exports.adminToggleTeacherActive = async (req, res) => {
  try {
    const { id } = req.params;
    const teacher = await User.findById(id);

    if (!teacher || teacher.role !== "teacher") {
      return res.status(404).json({ message: "Enseignant introuvable." });
    }

    teacher.isActive = !teacher.isActive;
    await teacher.save();

    return res.json({
      message: `Enseignant ${teacher.isActive ? "activé" : "désactivé"} avec succès.`,
      isActive: teacher.isActive,
    });
  } catch (err) {
    console.error("adminToggleTeacherActive error:", err);
    return res.status(500).json({ message: "Erreur serveur lors de la mise à jour du statut." });
  }
};

/* ===========================
   ADMIN: supprimer un enseignant
   DELETE /api/admin/teachers/:id
=========================== */
exports.adminDeleteTeacher = async (req, res) => {
  try {
    const { id } = req.params;

    const teacher = await User.findById(id);
    if (!teacher || teacher.role !== "teacher") {
      return res.status(404).json({ message: "Enseignant introuvable." });
    }

    await User.findByIdAndDelete(id);
    return res.json({ message: "🗑️ Enseignant supprimé avec succès." });
  } catch (err) {
    console.error("adminDeleteTeacher error:", err);
    return res.status(500).json({ message: "Erreur serveur lors de la suppression." });
  }
};

