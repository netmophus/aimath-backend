// const Message = require("../models/Message");

// const uploadChatFile = async (req, res) => {
//   try {
//     const senderId = req.user._id;
//     const { to } = req.body;

//     if (!req.file || !to) {
//       return res.status(400).json({ message: "Fichier ou destinataire manquant." });
//     }

//     // ✅ Conversion du mimetype en fileType standardisé
//     let fileType = "";

//     if (req.file.mimetype.startsWith("image")) {
//       fileType = "image";
//     } else if (req.file.mimetype === "application/pdf") {
//       fileType = "pdf";
//     } else if (req.file.mimetype.startsWith("video")) {
//       fileType = "video";
//     } else {
//       return res.status(400).json({ message: "Type de fichier non supporté." });
//     }

//     const newMessage = await Message.create({
//       from: senderId,
//       to,
//       text: "",
//       fileUrl: req.file.path,
//       fileType,
//       isVoiceMessage: false,
//     });

//     res.status(201).json(newMessage);
//   } catch (err) {
//     console.error("Erreur lors de l’envoi du fichier :", err);
//     res.status(500).json({ message: "Erreur serveur lors de l’envoi du fichier." });
//   }
// };

// module.exports = { uploadChatFile };

