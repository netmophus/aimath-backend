const SupportRequest = require("../models/SupportRequest");
const User = require("../models/userModel");
const Message = require("../models/Message");
const StudentProfile = require('../models/studentProfileModel'); // à adapter selon ton chemin
const MessageNotification = require("../models/MessageNotification"); // ✅ à ajouter si pas encore fait
const cloudinary = require("../config/cloudinary"); // ✅ Pour supprimer les fichiers


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
    console.log("🔍 Chargement des élèves pour enseignant :", teacherId);

    const activeRequests = await SupportRequest.find({
      teacher: teacherId,
      status: "acceptee",
      sessionStarted: true,
    }).populate("student", "_id fullName phone schoolName city photo");

    console.log("📋 Requêtes actives trouvées :", activeRequests.length);

    // Pour chaque élève, récupérer aussi son StudentProfile
    const students = await Promise.all(
      activeRequests.map(async (request) => {
        if (!request.student) {
          console.warn("⚠️ Student null dans request:", request._id);
          return null;
        }

        const student = request.student;
        let profile = null;
        
        try {
          profile = await StudentProfile.findOne({ user: student._id });
        } catch (profileErr) {
          console.warn("⚠️ Erreur récupération profil pour", student._id, profileErr.message);
        }

        return {
          ...student.toObject(),
          profile, // contient classe, balance, etc.
        };
      })
    );

    // Filtrer les valeurs null
    const validStudents = students.filter(s => s !== null);
    console.log("✅ Élèves valides retournés :", validStudents.length);

    res.json(validStudents);
  } catch (err) {
    console.error("❌ Erreur chargement élèves :", err);
    res.status(500).json({ message: "Erreur lors du chargement des élèves.", error: err.message });
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

      // ✅ Création de la notification pour l'élève
    await MessageNotification.create({
      user: to, // 👈 élève destinataire
      from: teacherId,
      messageId: newMsg._id,
      messageSnippet: text.slice(0, 100),
    });

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

    console.log("📎 Fichier reçu :", {
      name: req.file?.originalname,
      mimetype: req.file?.mimetype,
      size: req.file?.size,
      url: req.file?.secure_url
    });

    let fileType = "";
    const mime = req.file.mimetype;

    console.log("🔍 Détection du type de fichier :", { mimetype: mime });

    if (mime.startsWith("image")) {
      fileType = "image";
      console.log("✅ Type détecté : IMAGE");
    } else if (mime === "application/pdf") {
      fileType = "pdf";
      console.log("✅ Type détecté : PDF");
    } else if (mime.startsWith("video")) {
      fileType = "video";
      console.log("✅ Type détecté : VIDEO");
    } else if (mime.startsWith("audio")) {
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

    const newMessage = await Message.create({
      from: senderId,
      to,
      text: "",
      fileUrl,
      fileType,
      isVoiceMessage: fileType === "audio",
    });

    console.log("💾 Message créé :", {
      _id: newMessage._id,
      fileType: newMessage.fileType,
      fileUrl: newMessage.fileUrl,
      from: newMessage.from,
      to: newMessage.to
    });

    // ✅ Populate les infos de l'expéditeur et du destinataire
    await newMessage.populate("from", "_id fullName photo");
    await newMessage.populate("to", "_id fullName photo");

    console.log("📤 Message final envoyé :", {
      _id: newMessage._id,
      fileType: newMessage.fileType,
      fileUrl: newMessage.fileUrl,
      from: newMessage.from?.fullName,
      to: newMessage.to?.fullName
    });

    // ✅ Création de la notification pour l'élève
    await MessageNotification.create({
      user: to, // 👈 élève destinataire
      from: senderId,
      messageId: newMessage._id,
      messageSnippet: fileType === "image" ? "📷 Image" : fileType === "audio" ? "🎤 Message vocal" : `📎 ${fileType}`,
    });

    res.status(201).json(newMessage);
  } catch (err) {
    console.error("Erreur uploadChatFile :", err);
    res.status(500).json({ message: "Erreur serveur lors de l'envoi du fichier." });
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







// ✅ Fonction utilitaire pour extraire le public_id depuis une URL Cloudinary
const extractPublicIdFromUrl = (url) => {
  try {
    // Exemple d'URL: https://res.cloudinary.com/demo/image/upload/v1234567890/chat/files/1234567890-audioMessage.webm
    const parts = url.split('/');
    const uploadIndex = parts.indexOf('upload');
    if (uploadIndex === -1) return null;
    
    // Récupérer tout après "upload/vXXXXXXXXXX/"
    const pathParts = parts.slice(uploadIndex + 2); // Sauter "upload" et "vXXXXXXXXXX"
    const fullPath = pathParts.join('/');
    
    // Retirer l'extension
    const publicId = fullPath.replace(/\.[^/.]+$/, '');
    
    console.log("🔍 Public ID extrait :", publicId);
    return publicId;
  } catch (err) {
    console.error("❌ Erreur extraction public_id :", err);
    return null;
  }
};

// ✅ Supprimer un message (MongoDB + Cloudinary)
const deleteMessage = async (req, res) => {
  try {
    const teacherId = req.user._id;
    const { messageId } = req.params;

    console.log(`🗑️ Tentative de suppression du message ${messageId} par ${teacherId}`);

    // 1. Récupérer le message
    const message = await Message.findById(messageId);
    if (!message) {
      return res.status(404).json({ message: "Message introuvable." });
    }

    // 2. Vérifier que c'est bien l'enseignant qui a envoyé le message
    if (message.from.toString() !== teacherId.toString()) {
      return res.status(403).json({ message: "Vous ne pouvez supprimer que vos propres messages." });
    }

    // 3. Vérifier que l'enseignant a bien accès à cette conversation
    const isAllowed = await SupportRequest.findOne({
      teacher: teacherId,
      student: message.to,
      status: "acceptee",
      sessionStarted: true,
    });

    if (!isAllowed) {
      return res.status(403).json({ message: "Accès non autorisé à cette conversation." });
    }

    // 4. Supprimer le fichier de Cloudinary si présent
    if (message.fileUrl) {
      console.log("📁 Fichier détecté, suppression de Cloudinary...");
      const publicId = extractPublicIdFromUrl(message.fileUrl);
      
      if (publicId) {
        try {
          // Déterminer le resource_type selon le fileType
          let resourceType = "image";
          if (message.fileType === "video") {
            resourceType = "video";
          } else if (message.fileType === "audio") {
            resourceType = "video"; // Cloudinary stocke l'audio comme video
          } else if (message.fileType === "pdf") {
            resourceType = "raw";
          }

          console.log(`🗑️ Suppression Cloudinary - Type: ${resourceType}, ID: ${publicId}`);
          
          const result = await cloudinary.uploader.destroy(publicId, { 
            resource_type: resourceType 
          });
          
          console.log("✅ Résultat suppression Cloudinary :", result);
        } catch (cloudErr) {
          console.error("⚠️ Erreur suppression Cloudinary (on continue quand même) :", cloudErr);
          // On continue même si la suppression Cloudinary échoue
        }
      }
    }

    // 5. Supprimer le message de MongoDB
    await Message.findByIdAndDelete(messageId);
    console.log("✅ Message supprimé de MongoDB");

    res.json({ 
      success: true, 
      message: "Message supprimé avec succès.",
      messageId 
    });
  } catch (err) {
    console.error("❌ Erreur deleteMessage :", err);
    res.status(500).json({ message: "Erreur lors de la suppression du message." });
  }
};

module.exports = {
  getAvailableStudents,
  getChatMessagesWithStudent,
  sendMessageToStudent,
  uploadChatFile,
  getSupportRequestStatsForTeacher,
  deleteMessage, // ✅ Nouvelle fonction
};
