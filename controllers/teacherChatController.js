const SupportRequest = require("../models/SupportRequest");
const User = require("../models/userModel");
const Message = require("../models/Message");
const StudentProfile = require('../models/studentProfileModel'); // à adapter selon ton chemin


// 📌 1. Récupérer les élèves associés à l'enseignant avec session active
// const getAvailableStudents = async (req, res) => {
//   try {
//     const teacherId = req.user._id;

//     const activeRequests = await SupportRequest.find({
//       teacher: teacherId,
//       status: "acceptee",
//       sessionStarted: true,
//     }).populate("student", "_id fullName phone schoolName city classLevel photo");

//     const students = activeRequests.map((req) => req.student);
//     res.json(students);
//   } catch (err) {
//     console.error("Erreur chargement élèves :", err);
//     res.status(500).json({ message: "Erreur lors du chargement des élèves." });
//   }
// };




// 📌 2. Récupérer les messages entre l'enseignant et un élève


const getAvailableStudents = async (req, res) => {
  try {
    const teacherId = req.user._id;

    const activeRequests = await SupportRequest.find({
      teacher: teacherId,
      status: "acceptee",
      sessionStarted: true,
    }).populate("student", "_id fullName phone schoolName city photo");

    // Pour chaque élève, récupérer aussi son StudentProfile
    const students = await Promise.all(
      activeRequests.map(async (request) => {
        const student = request.student;
        const profile = await StudentProfile.findOne({ user: student._id });

        return {
          ...student.toObject(),
          profile, // contient classe, balance, etc.
        };
      })
    );

    res.json(students);
  } catch (err) {
    console.error("Erreur chargement élèves :", err);
    res.status(500).json({ message: "Erreur lors du chargement des élèves." });
  }
};




const getChatMessagesWithStudent = async (req, res) => {
  try {
    const teacherId = req.user._id;
    const studentId = req.params.studentId;

    const request = await SupportRequest.findOne({
      teacher: teacherId,
      student: studentId,
      status: "acceptee",
      sessionStarted: true,
    });

    if (!request) {
      return res.status(403).json({ message: "Accès non autorisé à cet élève." });
    }

    const messages = await Message.find({
      $or: [
        { from: teacherId, to: studentId },
        { from: studentId, to: teacherId },
      ],
    })
      .sort({ createdAt: 1 })
      .populate("from", "_id fullName photo")
      .populate("to", "_id fullName photo");

    res.json(messages);
  } catch (err) {
    console.error("Erreur getChatMessagesWithStudent:", err);
    res.status(500).json({ message: "Erreur lors du chargement des messages." });
  }
};



// 📌 3. Envoyer un message à un élève
const sendMessageToStudent = async (req, res) => {
  try {
    const teacherId = req.user._id;
    const { to, text } = req.body;

    const isAllowed = await SupportRequest.findOne({
      teacher: teacherId,
      student: to,
      status: "acceptee",
      sessionStarted: true,
    });

    if (!isAllowed) {
      return res.status(403).json({ message: "Vous ne pouvez pas envoyer de message à cet élève." });
    }

    const newMsg = new Message({
      from: teacherId,
      to,
      text,
    });

    await newMsg.save();
    await newMsg.populate("from", "_id fullName photo");
    await newMsg.populate("to", "_id fullName photo");

    res.status(201).json(newMsg);
  } catch (err) {
    console.error("Erreur sendMessageToStudent:", err);
    res.status(500).json({ message: "Erreur lors de l'envoi du message." });
  }
};






// const uploadChatFile = async (req, res) => {
//   try {
//     const senderId = req.user._id;
//     const { to } = req.body;

//     const isAllowed = await SupportRequest.findOne({
//       teacher: senderId,
//       student: to,
//       status: "acceptee",
//       sessionStarted: true,
//     });

//     if (!isAllowed) {
//       return res.status(403).json({ message: "Vous ne pouvez pas envoyer un fichier à cet élève." });
//     }

//     if (!req.file) {
//       return res.status(400).json({ message: "Aucun fichier reçu." });
//     }

//     let fileType = "";
//     const mime = req.file.mimetype;

//     if (mime.startsWith("image")) {
//       fileType = "image";
//     } else if (mime === "application/pdf") {
//       fileType = "pdf";
//     } else if (mime.startsWith("video")) {
//       fileType = "video";
//     } else if (mime.startsWith("audio")) {
//       fileType = "audio";
//     } else {
//       return res.status(400).json({ message: "Type de fichier non supporté." });
//     }

//     const fileUrl = req.file?.url || req.file?.path;
//     if (!fileUrl) {
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

//     res.status(201).json(newMessage);
//   } catch (err) {
//     console.error("Erreur uploadChatFile :", err);
//     res.status(500).json({ message: "Erreur serveur lors de l’envoi du fichier." });
//   }
// };

const uploadChatFile = async (req, res) => {
  try {
    const senderId = req.user._id;
    const { to } = req.body;

    const isAllowed = await SupportRequest.findOne({
      teacher: senderId,
      student: to,
      status: "acceptee",
      sessionStarted: true,
    });

    if (!isAllowed) {
      return res.status(403).json({ message: "Vous ne pouvez pas envoyer un fichier à cet élève." });
    }

    if (!req.file) {
      return res.status(400).json({ message: "Aucun fichier reçu." });
    }

    console.log("📎 Fichier reçu :", req.file); // ➕ Ajout de log utile

    let fileType = "";
    const mime = req.file.mimetype;

    if (mime.startsWith("image")) {
      fileType = "image";
    } else if (mime === "application/pdf") {
      fileType = "pdf";
    } else if (mime.startsWith("video")) {
      fileType = "video";
    } else if (mime.startsWith("audio")) {
      fileType = "audio";
    } else {
      return res.status(400).json({ message: "Type de fichier non supporté." });
    }

    const fileUrl = req.file?.secure_url || req.file?.path;
    if (!fileUrl) {
      return res.status(500).json({ message: "L’URL du fichier est manquante." });
    }

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
    console.error("Erreur uploadChatFile :", err);
    res.status(500).json({ message: "Erreur serveur lors de l’envoi du fichier." });
  }
};



// const getSupportRequestStatsForTeacher = async (req, res) => {
//   try {
//     const teacherId = req.user._id;

//     const stats = await SupportRequest.aggregate([
//       { $match: { teacher: teacherId } },
//       {
//         $group: {
//           _id: "$status",
//           count: { $sum: 1 },
//         },
//       },
//     ]);

//     // Transforme en format clé/valeur
//     const result = {
//       en_attente: 0,
//       acceptee: 0,
//       refusee: 0,
//       terminee: 0,
//     };

//     stats.forEach((s) => {
//       result[s._id] = s.count;
//     });

//     res.json(result);
//   } catch (error) {
//     console.error("Erreur statistiques soutien:", error);
//     res.status(500).json({ message: "Erreur serveur" });
//   }
// };



const getSupportRequestStatsForTeacher = async (req, res) => {
  try {
    const teacherId = req.user._id;

    // Récupère toutes les requêtes pertinentes (attribuées OU non attribuées)
    const allRelevantRequests = await SupportRequest.find({
      $or: [
        { teacher: teacherId },
        { teacher: null, status: "en_attente" } // important : les en_attente non encore assignées
      ]
    });

    // Initialisation
    const result = {
      en_attente: 0,
      acceptee: 0,
      refusee: 0,
      terminee: 0,
    };

    // Compte par statut
    allRelevantRequests.forEach(req => {
      if (result[req.status] !== undefined) {
        result[req.status]++;
      }
    });

    res.json(result);
  } catch (error) {
    console.error("Erreur statistiques soutien:", error);
    res.status(500).json({ message: "Erreur serveur" });
  }
};







module.exports = {
  getAvailableStudents,
  getChatMessagesWithStudent,
  sendMessageToStudent,
  uploadChatFile,
  getSupportRequestStatsForTeacher
};
