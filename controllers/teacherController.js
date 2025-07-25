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



