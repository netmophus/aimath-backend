const Message = require("../models/Message");
const User = require("../models/userModel");
const Teacher = require("../models/Teacher"); // 👈 Assure-toi que ce modèle est bien importé

const SupportRequest = require("../models/SupportRequest");
const MessageHistory = require("../models/MessageHistory");







// const getMessageHistory = async (req, res) => {
//   const { teacher, student } = req.query;

//   try {
//     const messages = await MessageHistory.find({
//       $or: [
//         { from: teacher, to: student },
//         { from: student, to: teacher },
//       ],
//     }).sort({ createdAt: 1 });

//     res.status(200).json(messages);
//   } catch (error) {
//     console.error("❌ Erreur récupération historique :", error);
//     res.status(500).json({ message: "Erreur serveur" });
//   }
// };




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



// const getAvailableTeachers = async (req, res) => {
//   try {
//     const studentId = req.user._id;

//     // Trouver tous les enseignants ayant accepté une requête de cet élève et démarré une session
//     const validRequests = await SupportRequest.find({
//       student: studentId,
//       status: "acceptee",
//       sessionStarted: true,
//     }).populate("teacher", "fullName photo city schoolName subjects levels");

//     // Extraire les enseignants sans doublon
//     const teachers = validRequests
//       .map((req) => req.teacher)
//       .filter((t) => t); // supprime les null si jamais

//     res.json(teachers);
//   } catch (err) {
//     console.error("Erreur getAvailableTeachers:", err);
//     res.status(500).json({ message: "Erreur lors du chargement des enseignants." });
//   }
// };



// 📩 Récupérer les messages avec un enseignant donné
// 📩 Récupérer les messages avec un enseignant donné

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

    await newMessage.populate("from", "_id fullName");
    await newMessage.populate("to", "_id fullName");

    res.status(201).json(newMessage);
  } catch (err) {
    res.status(500).json({ message: "Erreur lors de l’envoi du message." });
  }
};





// const uploadChatFile = async (req, res) => {
//   try {
//     console.log("🟢 Étape 1 - Entrée dans uploadChatFile");
//     const senderId = req.user._id;
//     const { to } = req.body;

//     console.log("🔵 Étape 2 - Contenu de req.user :", req.user);
//     console.log("🔵 Étape 3 - Contenu de req.body :", req.body);

//     if (!req.file) {
//       console.error("❌ Étape 4 - Aucun fichier reçu dans req.file");
//       return res.status(400).json({ message: "Aucun fichier reçu." });
//     }

//     console.log("🟡 Étape 5 - Contenu complet de req.file :");
//     console.dir(req.file, { depth: null });

//     if (!to) {
//       console.error("❌ Étape 6 - Champ 'to' manquant dans req.body");
//       return res.status(400).json({ message: "Destinataire manquant." });
//     }

//     let fileType = "";
//     const mime = req.file.mimetype;
//     console.log("🟣 Étape 7 - mimetype détecté :", mime);

//     if (mime.startsWith("image")) {
//       fileType = "image";
//     } else if (mime === "application/pdf") {
//       fileType = "pdf";
//     } else if (mime.startsWith("video")) {
//       fileType = "video";
//     } else if (mime.startsWith("audio")) {
//       fileType = "audio";
//     } else {
//       console.error("❌ Étape 8 - Type de fichier non supporté :", mime);
//       return res.status(400).json({ message: "Type de fichier non supporté." });
//     }

//     const fileUrl = req.file?.url || req.file?.path;
//     console.log("🟤 Étape 9 - fileUrl détecté :", fileUrl);

//     if (!fileUrl) {
//       console.error("❌ Étape 10 - fileUrl manquant");
//       return res.status(500).json({ message: "L’URL du fichier est manquante." });
//     }

//     const newMessage = await Message.create({
//       from: senderId,
//       to,
//       text: "",
//       fileUrl,
//       fileType,
//       isVoiceMessage: fileType === "audio",
//     });

//     console.log("🟢 Étape 11 - Message sauvegardé :", newMessage);
//     res.status(201).json(newMessage);
//   } catch (err) {
//     console.error("❌ Étape 12 - Exception :", err.message);
//     console.error(err.stack);
//     res.status(500).json({ message: "Erreur serveur lors de l’envoi du fichier." });
//   }
// };



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

    // 📁 Détection du type de fichier
    let fileType = "";
    const mime = req.file.mimetype;

    if (mime.startsWith("image")) fileType = "image";
    else if (mime === "application/pdf") fileType = "pdf";
    else if (mime.startsWith("video")) fileType = "video";
    else if (
  mime.startsWith("audio") ||
  mime === "audio/webm" ||
  mime === "audio/m4a" ||
  mime === "audio/mp4" ||
  mime === "audio/x-m4a"
) fileType = "audio";

    else return res.status(400).json({ message: "Type de fichier non supporté." });

    const fileUrl = req.file?.url || req.file?.path;
    if (!fileUrl) {
      return res.status(500).json({ message: "L’URL du fichier est manquante." });
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

    res.status(201).json(newMessage);
  } catch (err) {
    console.error("❌ Erreur uploadChatFile (élève) :", err.message);
    res.status(500).json({ message: "Erreur serveur lors de l’envoi du fichier." });
  }
};



module.exports = {
  getAvailableTeachers,
  getMessagesWithTeacher,
  sendMessageToTeacher,
  uploadChatFile,
 getMessageHistory,

};
