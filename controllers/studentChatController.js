const Message = require("../models/Message");
const User = require("../models/userModel");
const Teacher = require("../models/Teacher"); // 👈 Assure-toi que ce modèle est bien importé

const SupportRequest = require("../models/SupportRequest");
const MessageHistory = require("../models/MessageHistory");

const MessageNotification = require("../models/MessageNotification"); // <-- à importer







const getMessageHistory = async (req, res) => {
  const { teacher, student, request } = req.query;

  try {
    if (!teacher || !student) {
      return res.status(400).json({ message: "Paramètres manquants." });
    }

    const baseFilter = {
      $or: [
        { from: teacher, to: student },
        { from: student, to: teacher },
      ],
    };

    // ✅ Si request est valide, filtrer par originalRequest
    if (request && request !== "null") {
      baseFilter.originalRequest = request;
    }

    const messages = await MessageHistory.find(baseFilter).sort({ createdAt: 1 });

    res.status(200).json(messages);
  } catch (error) {
    console.error("❌ Erreur récupération historique :", error);
    res.status(500).json({ message: "Erreur serveur" });
  }
};



const getAvailableTeachers = async (req, res) => {
  try {
    const studentId = req.user._id;

    const validRequests = await SupportRequest.find({
      student: studentId,
      status: "acceptee",
      sessionStarted: true,
    }).populate("teacher"); // ça donne des objets User

    const userTeachers = validRequests.map((req) => req.teacher).filter((t) => t);

    // Charger les infos depuis la collection Teacher
    const teacherDetails = await Teacher.find({
      userId: { $in: userTeachers.map((u) => u._id) },
    });

    // Fusionner les données User + Teacher
    const combined = userTeachers.map((user) => {
      const extra = teacherDetails.find((t) => t.userId.toString() === user._id.toString());
      return {
        ...user.toObject(),
        subjects: extra?.subjects || [],
        levels: extra?.levels || [],
      };
    });

    res.json(combined);
  } catch (err) {
    console.error("Erreur getAvailableTeachers:", err);
    res.status(500).json({ message: "Erreur lors du chargement des enseignants." });
  }
};





const getMessagesWithTeacher = async (req, res) => {
  const teacherId = req.params.teacherId;
  const studentId = req.user._id;

  try {
    const hasAccess = await SupportRequest.findOne({
      student: studentId,
      teacher: teacherId,
      status: "acceptee",
      sessionStarted: true,
    });

    if (!hasAccess) {
      return res.status(403).json({ message: "Accès refusé : pas de session active avec cet enseignant." });
    }

    const messages = await Message.find({
      $or: [
        { from: studentId, to: teacherId },
        { from: teacherId, to: studentId },
      ],
    })
      .sort("createdAt")
      .populate("from", "_id fullName")
      .populate("to", "_id fullName");

    res.json(messages);
  } catch (err) {
    res.status(500).json({ message: "Erreur lors du chargement des messages." });
  }
};



// ✉️ Envoyer un message à un enseignant
const sendMessageToTeacher = async (req, res) => {
  const studentId = req.user._id;
  const { to, text } = req.body;

  if (!to || !text) {
    return res.status(400).json({ message: "Champs requis manquants." });
  }

  const hasAccess = await SupportRequest.findOne({
    student: studentId,
    teacher: to,
    status: "acceptee",
    sessionStarted: true,
  });

  if (!hasAccess) {
    return res.status(403).json({ message: "Vous ne pouvez pas envoyer de message à cet enseignant." });
  }

  try {
    const newMessage = await Message.create({
      from: studentId,
      to,
      text,
      isVoiceMessage: false,
    });



        // ✅ Créer une notification pour l'enseignant
    await MessageNotification.create({
      user: to, // destinataire = l'enseignant
      from: studentId, // expéditeur = l'élève
      messageId: newMessage._id,
      messageSnippet: text.substring(0, 50), // extrait du message
    });


    await newMessage.populate("from", "_id fullName");
    await newMessage.populate("to", "_id fullName");

    res.status(201).json(newMessage);
  } catch (err) {
    res.status(500).json({ message: "Erreur lors de l’envoi du message." });
  }
};







const uploadChatFile = async (req, res) => {
  try {
    const senderId = req.user._id;
    const { to } = req.body;

    if (!req.file || !to) {
      return res.status(400).json({ message: "Fichier ou destinataire manquant." });
    }

    // 🔒 Vérification que le chat est autorisé
    const hasAccess = await SupportRequest.findOne({
      student: senderId,
      teacher: to,
      status: "acceptee",
      sessionStarted: true,
    });

    if (!hasAccess) {
      return res.status(403).json({ message: "Vous n'avez pas de session active avec cet enseignant." });
    }

    console.log("📎 Fichier reçu (étudiant) :", {
      name: req.file?.originalname,
      mimetype: req.file?.mimetype,
      size: req.file?.size,
      url: req.file?.secure_url
    });

    // 📁 Détection du type de fichier
    let fileType = "";
    const mime = req.file.mimetype;

    console.log("🔍 Détection du type de fichier (étudiant) :", { mimetype: mime });

    if (mime.startsWith("image")) {
      fileType = "image";
      console.log("✅ Type détecté : IMAGE");
    } else if (mime === "application/pdf") {
      fileType = "pdf";
      console.log("✅ Type détecté : PDF");
    } else if (mime.startsWith("video")) {
      fileType = "video";
      console.log("✅ Type détecté : VIDEO");
    } else if (
      mime.startsWith("audio") ||
      mime === "audio/webm" ||
      mime === "audio/m4a" ||
      mime === "audio/mp4" ||
      mime === "audio/x-m4a"
    ) {
      fileType = "audio";
      console.log("✅ Type détecté : AUDIO");
    } else {
      console.log("❌ Type non supporté :", mime);
      return res.status(400).json({ message: "Type de fichier non supporté." });
    }

    const fileUrl = req.file?.secure_url || req.file?.path;
    if (!fileUrl) {
      return res.status(500).json({ message: "L'URL du fichier est manquante." });
    }

    // 📩 Création du message avec fichier
    const newMessage = await Message.create({
      from: senderId,
      to,
      text: "",
      fileUrl,
      fileType,
      isVoiceMessage: fileType === "audio",
    });

    console.log("💾 Message créé (étudiant) :", {
      _id: newMessage._id,
      fileType: newMessage.fileType,
      fileUrl: newMessage.fileUrl,
      from: newMessage.from,
      to: newMessage.to
    });

    // ✅ Populate les infos de l'expéditeur et du destinataire
    await newMessage.populate("from", "_id fullName photo");
    await newMessage.populate("to", "_id fullName photo");

    console.log("📤 Message final envoyé (étudiant) :", {
      _id: newMessage._id,
      fileType: newMessage.fileType,
      fileUrl: newMessage.fileUrl,
      from: newMessage.from?.fullName,
      to: newMessage.to?.fullName
    });

    // ✅ Création de la notification pour l'enseignant
    await MessageNotification.create({
      user: to, // 👈 enseignant destinataire
      from: senderId, // 👈 élève expéditeur
      messageId: newMessage._id,
      messageSnippet: fileType === "image" ? "📷 Image" : fileType === "audio" ? "🎤 Message vocal" : `📎 ${fileType}`,
    });

    res.status(201).json(newMessage);
  } catch (err) {
    console.error("❌ Erreur uploadChatFile (élève) :", err.message);
    res.status(500).json({ message: "Erreur serveur lors de l'envoi du fichier." });
  }
};



module.exports = {
  getAvailableTeachers,
  getMessagesWithTeacher,
  sendMessageToTeacher,
  uploadChatFile,
 getMessageHistory,

};
