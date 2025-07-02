const User = require("../models/userModel");
const PaymentHistory = require("../models/PaymentHistory");

const simulatePayment = async (req, res) => {
  const { phone, amount, reference } = req.body;

  try {
    const user = await User.findOne({ phone });
    if (!user) return res.status(404).json({ message: "Utilisateur non trouvé." });

    let duration;
    if (amount === 2000) duration = 30;
    else if (amount === 15000) duration = 365;
    else return res.status(400).json({ message: "Montant non valide." });

    const startDate = new Date();
    const endDate = new Date();
    endDate.setDate(startDate.getDate() + duration);

    // ✅ Mise à jour du statut d'abonnement
    user.isSubscribed = true;
    user.subscriptionStart = startDate;
    user.subscriptionEnd = endDate;
    await user.save();

    // ✅ Enregistrement dans PaymentHistory
    const payment = await PaymentHistory.create({
      phone: user.phone,
      user: user._id,
      amount,
      reference,
      paidAt: new Date()
    });

    // ✅ Log clair pour surveillance
    console.log("✅ Paiement simulé enregistré :", {
      user: user.fullName,
      phone,
      amount,
      reference,
      start: startDate.toISOString(),
      end: endDate.toISOString()
    });

    res.json({ message: "Abonnement activé avec succès." });
  } catch (error) {
    console.error("❌ Erreur simulatePayment :", error.message);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

module.exports = { simulatePayment };
