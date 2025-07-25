const express = require("express");
const router = express.Router();
const {
  getAvailableTeachers,
  getMessagesWithTeacher,
  sendMessageToTeacher,
  uploadChatFile,
  getMessageHistory,
} = require("../controllers/studentChatController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const uploadChat = require("../middlewares/uploadChat");


// 👨‍🎓 Accès uniquement pour les élèves authentifiés
router.use(authMiddleware, authorizeRoles("eleve"));

// 🔁 Liste des enseignants disponibles pour discuter
router.get("/chat-teachers", getAvailableTeachers);

// 📩 Récupérer la discussion avec un enseignant
router.get("/chat/:teacherId", getMessagesWithTeacher);

// ✉️ Envoyer un message à un enseignant
router.post("/chat/send", sendMessageToTeacher);

// router.post("/chat/upload", authMiddleware, uploadChat, uploadChatFile);
router.post("/chat/upload", authMiddleware, (req, res, next) => {
  uploadChat(req, res, function (err) {
    console.log("✅ uploadChat appelé");
    if (err) {
      console.error("❌ Erreur dans uploadChat (middleware multer):", err.message);
      return res.status(500).json({ message: "Erreur de téléchargement : " + err.message });
    }
    next();
  });
}, uploadChatFile);




// 📚 🔒 Historique consultable uniquement si session terminée
router.get(
  "/messages/history",
  authMiddleware,
  authorizeRoles("eleve"),
  getMessageHistory
);



module.exports = router;
