
const express = require("express");
const router = express.Router();
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const uploadChat = require("../middlewares/uploadChat");
const {
  getAvailableStudents,
  getChatMessagesWithStudent,
  sendMessageToStudent,
  uploadChatFile,
  getSupportRequestStatsForTeacher,

} = require("../controllers/teacherChatController");

// Authentification + Autorisation
router.use(authMiddleware, authorizeRoles("teacher"));

// Routes
router.get("/chat-students", getAvailableStudents);
router.get("/chat/:studentId", getChatMessagesWithStudent);
router.post("/chat/send", sendMessageToStudent);

// Exemple de route
router.post("/chat/upload", authMiddleware, uploadChat, uploadChatFile);

router.get("/support-requests/stats", authMiddleware, getSupportRequestStatsForTeacher);


// ✅ Export correct
module.exports = router;
