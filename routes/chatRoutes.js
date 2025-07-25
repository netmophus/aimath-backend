// const express = require("express");
// const router = express.Router();

// const { sendMessage, getMessages } = require("../controllers/chatController");
// const authMiddleware = require("../middlewares/authMiddleware");
// const { authorizeRoles } = require("../middlewares/roleMiddleware");

// // ✅ Envoyer un message (élève ↔ enseignant)
// router.post(
//   "/send",
//   authMiddleware,
//   authorizeRoles("eleve", "teacher"),
//   sendMessage
// );

// // ✅ Récupérer tous les messages avec un utilisateur donné
// router.get(
//   "/:userId",
//   authMiddleware,
//   authorizeRoles("eleve", "teacher"),
//   getMessages
// );

// module.exports = router;



// const express = require("express");
// const router = express.Router();

// const authMiddleware = require("../middlewares/authMiddleware");
// const uploadChat = require("../middlewares/uploadChat");
// const { uploadChatFile } = require("../controllers/chatController");

// // Exemple de route
// router.post("/upload", authMiddleware, uploadChat, uploadChatFile);

// module.exports = router; // ✅ IMPORTANT !
