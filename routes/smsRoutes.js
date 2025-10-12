const express = require("express");
const router = express.Router();
const { sendSMS } = require("../utils/sendSMS");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

// Route pour envoyer un SMS (partenaires et admins)
router.post(
  "/send",
  authMiddleware,
  authorizeRoles("partner", "admin"),
  async (req, res) => {
    try {
      const { to, message } = req.body;

      console.log("📱 Tentative envoi SMS à:", to);

      if (!to || !message) {
        return res.status(400).json({ message: "Numéro et message requis" });
      }

      const result = await sendSMS(to, message);

      if (result.success) {
        console.log("✅ SMS envoyé avec succès à:", to);
        res.json({ message: "SMS envoyé avec succès", data: result.data });
      } else {
        console.error("❌ Échec envoi SMS à:", to, result);
        res.status(500).json({ message: "Échec de l'envoi du SMS" });
      }
    } catch (error) {
      console.error("❌ Erreur envoi SMS:", error);
      res.status(500).json({ message: "Erreur serveur lors de l'envoi du SMS" });
    }
  }
);

module.exports = router;

