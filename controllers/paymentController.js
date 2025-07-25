const User = require("../models/userModel");
const PaymentHistory = require("../models/PaymentHistory");
const AccessCodeBatch = require("../models/AccessCodeBatch");
const { v4: uuidv4 } = require("uuid");


// const getAccessCodeStats = async (req, res) => {
//   try {
//     const users = await User.find();
//     const batches = await AccessCodeBatch.find();

//     const connectedUsers = users.length;
//     const registeredWithSubscription = users.filter(u => u.subscriptionActive).length;
//     const registeredWithoutSubscription = connectedUsers - registeredWithSubscription;

//     const batchStats = batches.map((batch) => {
//       const usedCards = batch.codes.filter(c => c.used).length;
//       const unusedCards = batch.totalCodes - usedCards;
//       const totalAmount = batch.totalCodes * batch.price;
//       const totalUsedAmount = usedCards * batch.price;
//       const totalUnusedAmount = unusedCards * batch.price;

//       return {
//         batchId: batch.batchId,
//         totalCards: batch.totalCodes,
//         pricePerCard: batch.price,
//         usedCards,
//         unusedCards,
//         totalAmount,
//         totalUsedAmount,
//         totalUnusedAmount
//       };
//     });

//     res.json({
//       connectedUsers,
//       registeredWithSubscription,
//       registeredWithoutSubscription,
//       batches: batchStats
//     });
//   } catch (error) {
//     console.error("Erreur stats :", error);
//     res.status(500).json({ message: "Erreur serveur lors du calcul des stats." });
//   }
// };

const getAccessCodeStats = async (req, res) => {
  try {
    const users = await User.find({ role: "eleve" });

    const batches = await AccessCodeBatch.find();

    const connectedUsers = users.length;

    const now = new Date();
    const registeredWithSubscription = users.filter(u =>
      u.isSubscribed &&
      u.subscriptionStart &&
      u.subscriptionEnd &&
      now >= u.subscriptionStart &&
      now <= u.subscriptionEnd
    ).length;

    const registeredWithoutSubscription = connectedUsers - registeredWithSubscription;

    const batchStats = batches.map((batch) => {
      const usedCards = batch.codes.filter(c => c.used).length;
      const unusedCards = batch.totalCodes - usedCards;
      const totalAmount = batch.totalCodes * batch.price;
      const totalUsedAmount = usedCards * batch.price;
      const totalUnusedAmount = unusedCards * batch.price;

      return {
        batchId: batch.batchId,
        totalCards: batch.totalCodes,
        pricePerCard: batch.price,
        usedCards,
        unusedCards,
        totalAmount,
        totalUsedAmount,
        totalUnusedAmount
      };
    });

    res.json({
      connectedUsers,
      registeredWithSubscription,
      registeredWithoutSubscription,
      batches: batchStats
    });
  } catch (error) {
    console.error("Erreur stats :", error);
    res.status(500).json({ message: "Erreur serveur lors du calcul des stats." });
  }
};




const generateCodes = async (req, res) => {
  try {
    const { type, quantity, price } = req.body;

    if (!["mensuel", "annuel"].includes(type)) {
      return res.status(400).json({ message: "Type invalide." });
    }

    if (!price || price <= 0) {
      return res.status(400).json({ message: "Prix invalide." });
    }

    const datePart = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    const randomPart = Math.floor(100 + Math.random() * 900);
    const batchId = `LOT-${datePart}-${randomPart}`;

    const now = new Date();
    const codes = [];

    for (let i = 0; i < quantity; i++) {
      codes.push({
      code: `FAH-${uuidv4().split("-")[0].toUpperCase()}`,
      status: "generated",
      used: false,
      usedBy: null,
      usedAt: null,
      createdAt: now,
      price: price // ✅ on ajoute ici le prix de la carte
    });

    }

    const batch = new AccessCodeBatch({
      batchId,
      type,
      generatedBy: req.user._id,
      codes,
      price,                         // ✅ prix au niveau du lot uniquement
      totalCodes: quantity,
    });

    await batch.save();

    res.status(201).json({
      message: `✅ ${quantity} codes générés dans le lot ${batchId}`,
      batchId,
    });
  } catch (err) {
    console.error("Erreur de génération :", err);
    res.status(500).json({ message: "Erreur serveur lors de la génération." });
  }
};




const getAllAccessCodes = async (req, res) => {
  try {
    const batches = await AccessCodeBatch.find()
      .populate("generatedBy", "fullName") // 🔥 On récupère le nom de l'utilisateur
      .sort({ createdAt: -1 });


      

    res.json(batches);
  } catch (error) {
    console.error("Erreur getAllAccessCodes :", error);
    res.status(500).json({ message: "Erreur lors du chargement des lots de codes." });
  }
};













const getCodesByBatch = async (req, res) => {
  const { batchId } = req.params;

  try {
    const batch = await AccessCodeBatch.findOne({ batchId })
      .populate("generatedBy", "fullName")
      .populate("codes.usedBy", "fullName phone schoolName city");

  //     const batch = await AccessCodeBatch.findOne({ batchId: req.params.batchId })
  // .populate("codes.usedBy", "phone schoolName city");


    if (!batch) {
      return res.status(404).json({ message: "Lot introuvable." });
    }

   res.json(batch); // 👈 pour avoir tout le lot + les codes + utilisateurs

  } catch (error) {
    console.error("Erreur getCodesByBatch :", error);
    res.status(500).json({ message: "Erreur lors du chargement du lot." });
  }
};






// const activateBatch = async (req, res) => {
//   try {
//     const { batchId } = req.body;

//     const batch = await AccessCodeBatch.findOne({ batchId });
//     if (!batch) {
//       return res.status(404).json({ message: "Lot introuvable." });
//     }

//     // Active toutes les cartes non utilisées
//     batch.codes = batch.codes.map(code =>
//       !code.used ? { ...code, activated: true } : code
//     );

//     await batch.save();

//     res.json({ message: "Tous les codes du lot ont été activés." });
//   } catch (error) {
//     console.error("Erreur lors de l’activation du lot :", error);
//     res.status(500).json({ message: "Erreur serveur lors de l’activation du lot." });
//   }
// };

const activateBatch = async (req, res) => {
  try {
    const { batchId } = req.body;

    const batch = await AccessCodeBatch.findOne({ batchId });
    if (!batch) {
      return res.status(404).json({ message: "Lot introuvable." });
    }

    // Mise à jour des statuts uniquement si le code n’est pas utilisé
    batch.codes = batch.codes.map(code =>
      !code.used && code.status === "generated"
        ? { ...code, status: "activated" }
        : code
    );

    await batch.save();

    res.json({ message: "✅ Tous les codes non utilisés ont été activés." });
  } catch (error) {
    console.error("Erreur lors de l’activation du lot :", error);
    res.status(500).json({ message: "Erreur serveur lors de l’activation du lot." });
  }
};




const redeemCode = async (req, res) => {
  const { code } = req.body;
  const userId = req.user._id;

  try {
    const normalizedCode = code.trim().toUpperCase();

    // 🔍 Trouver le lot contenant ce code
    const batch = await AccessCodeBatch.findOne({
      "codes.code": normalizedCode,
    });

    if (!batch) {
      return res.status(404).json({ message: "❌ Code invalide ou inexistant." });
    }

    // 🔍 Trouver le code dans le lot
    const targetCode = batch.codes.find((c) => c.code === normalizedCode);

    if (!targetCode) {
      return res.status(404).json({ message: "❌ Code introuvable." });
    }

    if (targetCode.used) {
      return res.status(400).json({ message: "⚠️ Ce code a déjà été utilisé." });
    }

    // 🕐 Calcule la durée en fonction du type de lot
    const now = new Date();
    const durationInDays = batch.type === "annuel" ? 365 : 30;
    const subscriptionEnd = new Date(now.getTime() + durationInDays * 24 * 60 * 60 * 1000);

    // ✅ Mettre à jour l’utilisateur
    await User.findByIdAndUpdate(userId, {
      isSubscribed: true,
      subscriptionStart: now,
      subscriptionEnd: subscriptionEnd,
      paymentReference: normalizedCode,
    });

    // ✅ Mettre à jour le code dans le lot
    targetCode.used = true;
    targetCode.status = "used"; // ou "activated" selon ta logique
    targetCode.usedBy = userId;
    targetCode.usedAt = now;

    await batch.save();

    res.status(200).json({ message: "✅ Code activé avec succès !" });
  } catch (error) {
    console.error("Erreur dans redeemCode :", error);
    res.status(500).json({ message: "❌ Erreur serveur lors de la validation du code." });
  }
};


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

module.exports = { simulatePayment, getAccessCodeStats, activateBatch , redeemCode, generateCodes, getAllAccessCodes, getCodesByBatch };
