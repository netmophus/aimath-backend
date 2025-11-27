const User = require("../models/userModel");
const PaymentHistory = require("../models/PaymentHistory");
const AccessCodeBatch = require("../models/AccessCodeBatch");
const { v4: uuidv4 } = require("uuid");
const { sendSMS } = require("../utils/sendSMS");
const { sendPaymentConfirmationEmail } = require("../utils/sendEmail");
const axios = require("axios");

const { maskCode } = require("../utils/mask");

// util local dans paymentController
const phoneForSMS = (raw = "") => {
  // 1) garder uniquement les chiffres
  let s = String(raw).replace(/\D/g, "");

  // 2) si format international "00", on retire juste les deux zéros
  //    0022796648383 -> 22796648383
  if (s.startsWith("00")) s = s.slice(2);

  // 3) si l'utilisateur met un 0 devant le numéro local (ex: 096648383),
  //    on le retire -> 96648383
  if (/^0\d{8}$/.test(s)) s = s.slice(1);

  // 4) 8 chiffres locaux -> on préfixe par l'indicatif Niger
  if (/^\d{8}$/.test(s)) s = "227" + s;

  // 5) si on a bien 227 + 8 chiffres, c'est parfait
  if (/^227\d{8}$/.test(s)) return s;

  // 6) sinon on log pour investigation, on renvoie quand même
  console.warn("⚠️ phoneForSMS format inattendu:", raw, "→", s);
  return s;
};



// ----- CONFIG NITA (prends des env vars si dispo, sinon valeurs par défaut) -----
const NITA_BASE_URL = process.env.NITA_BASE_URL || "https://payment.nitapiservices.com";
const NITA_API_KEY  = process.env.NITA_API_KEY  || "jF-GLQtShTidrX6Txx_J4HFJwB3GRk2S7V3OsFlSUSI";
const NITA_USERNAME = process.env.NITA_USERNAME || "SOFTLINKTEC";
const NITA_PASSWORD = process.env.NITA_PASSWORD || "SOFTLINKTEC@2025";

// ----- Helpers de parsing / normalisation -----
const parseNitaPaid = (raw) => {
  const v = String(raw ?? "").trim().toLowerCase();
  // accepte “1”, “success”, “succès”, “paid”, “ok”
  if (v === "1" || v === "success" || v === "succès" || v === "paid" || v === "ok") return 1;
  if (v === "2" || v.includes("cancel")) return 2;
  if (v === "3" || v.includes("block"))  return 3;
  if (v === "0" || v === "" || v.includes("pending") || v.includes("attente") || v.includes("process")) return 0;
  return -1;
};

const phoneToNitaServer = (raw = "") => {
  // on veut 00227XXXXXXXX
  let s = String(raw).replace(/\s+/g, "");
  if (!s) return "";
  if (s.startsWith("+"))  s = "00" + s.slice(1);
  if (s.startsWith("227")) s = "00" + s;
  if (/^\d{8}$/.test(s)) s = "00227" + s;
  return s;
};

// ----- Auth NITA -----
const nitaAuth = async () => {
  console.log("🔐 [NITA] auth →", NITA_BASE_URL + "/api/authenticate");
  const res = await axios.post(
    `${NITA_BASE_URL}/api/authenticate`,
    { username: NITA_USERNAME, password: NITA_PASSWORD },
    { headers: { "Content-Type": "application/json", "X-NT-API-KEY": NITA_API_KEY, Accept: "application/json" } }
  );
  const data = res.data || {};
  const token = data.token || data.access_token || data.jwt || data?.data?.token;
  if (!token) throw new Error("Auth NITA: token introuvable");
  console.log("🔐 [NITA] auth OK");
  return token;
};

// ----- Check achat NITA côté serveur -----
const nitaCheckAchatStatusServer = async ({ token, requestId, reference, phone }) => {
  const payload = {
    requestId: requestId || undefined,
    referenceAchat: reference || undefined,
    codeAchat: reference || undefined, // certains endpoints acceptent codeAchat
    phoneClient: phone ? phoneToNitaServer(phone) : undefined,
    adresseIp: "102.45.67.89",
  };

  console.log("🔎 [NITA] checkAchatStatus → payload", payload);

  const res = await axios.post(
    `${NITA_BASE_URL}/api/nitaServices/achatEnLigne/checkAchatStatus`,
    payload,
    {
      headers: {
        "Content-Type": "application/json",
        "X-NT-API-KEY": NITA_API_KEY,
        "Authorization": `Bearer ${token}`,
        Accept: "application/json",
      },
      validateStatus: () => true, // on log même si 4xx/5xx
    }
  );

  console.log("🔎 [NITA] checkAchatStatus ← http", res.status, typeof res.data === "object" ? JSON.stringify(res.data) : res.data);

  // compat : on va chercher un champ “status”
  const d = res.data || {};
  const raw = d.status ?? d.code ?? d?.data?.status ?? d?.data?.code ?? d?.statusTransaction ?? d?.etat;
  const status = Number.isFinite(+raw) ? (+raw) : parseNitaPaid(raw);

  return { http: res.status, body: d, status };
};

// ===== NOUVEAU CONTROLLER : check côté serveur puis active si payé =====
const checkNitaAndActivate = async (req, res) => {
  console.log("➡️  [/nita/check-and-activate] start");
  try {
    const userId = req.user?._id;
    const { requestId, reference, amount, plan } = req.body || {};

    console.log("🟡 Input =", { userId: userId?.toString?.(), requestId, reference, amount, plan });

    if (!requestId && !reference) {
      console.log("🔴 Missing requestId/reference");
      return res.status(400).json({ message: "requestId ou reference manquant." });
    }

    // 1) Auth NITA
    const jwt = await nitaAuth();

    // 2) Check status
    const { status, http, body } = await nitaCheckAchatStatusServer({
      token: jwt,
      requestId,
      reference,
      phone: req.user?.phone,
    });

    console.log("🧭 NITA status =", status, "(http =", http, ")");

    // 3) Si pas payé → retourne juste le statut (frontend continue le polling)
    if (status !== 1) {
      return res.status(200).json({
        paid: false,
        status,
        nitaHttp: http,
        nitaBody: body,
        message: "Paiement non confirmé pour l'instant."
      });
    }

    // 4) Si payé → active l'abonnement (réutilise ta logique “activateSubscription”)
    //    pour éviter la duplication, on le fait ici, en reprenant les mêmes règles :
    const refToStore = reference || requestId;

    // Idempotence
    const already = await PaymentHistory.findOne({ user: userId, reference: refToStore }).lean();
    if (already) {
      console.log("🟠 Déjà activé pour ref =", refToStore);
      const u = await User.findById(userId).select("subscriptionStart subscriptionEnd").lean();
      return res.status(200).json({
        paid: true,
        activated: true,
        message: "Déjà activé pour cette référence.",
        subscriptionStart: u?.subscriptionStart,
        subscriptionEnd: u?.subscriptionEnd
      });
    }

    // Charge l'utilisateur
    const user = await User.findById(userId);
    if (!user) {
      console.log("🔴 Utilisateur introuvable:", userId?.toString?.());
      return res.status(404).json({ message: "Utilisateur non trouvé." });
    }

    // Durée (mêmes règles)
    let days = 30;
    const p = String(plan || "").toLowerCase();
    if (p === "annuel" || Number(amount) >= 15000) days = 365;

    // Dates
    const now = new Date();
    const base = (user.subscriptionEnd && user.subscriptionEnd > now) ? user.subscriptionEnd : now;
    const newEnd = new Date(base.getTime() + days * 24 * 60 * 60 * 1000);

    // MAJ user
    user.isSubscribed = true;
    if (!user.subscriptionStart) user.subscriptionStart = now;
    user.subscriptionEnd = newEnd;
    user.paymentReference = refToStore;
    await user.save();
    console.log("✅ User MAJ via check-and-activate →", {
      userId: user._id?.toString?.(),
      subscriptionStart: user.subscriptionStart?.toISOString?.(),
      subscriptionEnd: user.subscriptionEnd?.toISOString?.(),
      paymentReference: user.paymentReference
    });

    // Historique
    const amountVal = Number(amount) || (p === "annuel" ? 20000 : 2000);
    try {
      const ph = await PaymentHistory.create({
        user: user._id,
        phone: user.phone,
        amount: amountVal,
        reference: refToStore,
        paidAt: new Date()
      });
      console.log("🧾 PaymentHistory (check-and-activate) →", ph._id?.toString?.(), amountVal, refToStore);
    } catch (e) {
      console.error("⚠️ PaymentHistory error:", e?.message);
    }

    // SMS
    try {
      const to = phoneForSMS(user.phone);
      const msg = `Fahimta: Votre abonnement est actif jusqu'au ${newEnd.toISOString().slice(0,10)}. Merci!`;
      const smsRes = await sendSMS(to, msg);
      console.log("📲 sendSMS (check-and-activate) →", smsRes);
    } catch (e) {
      console.error("⚠️ SMS error:", e?.message);
    }

    // Email (si l'utilisateur a un email)
    if (user.email) {
      try {
        const emailRes = await sendPaymentConfirmationEmail(user.email, {
          amount: amountVal,
          reference: refToStore,
          method: "NITA",
          subscriptionEnd: newEnd,
          plan: p === "annuel" || amountVal >= 15000 ? "annuel" : "mensuel",
        });
        console.log("📧 sendPaymentConfirmationEmail (check-and-activate) →", emailRes);
      } catch (e) {
        console.error("⚠️ Email error:", e?.message);
      }
    }

    console.log("🏁 [/nita/check-and-activate] done OK for", user._id?.toString?.());
    return res.status(200).json({
      paid: true,
      activated: true,
      message: "✅ Abonnement activé.",
      subscriptionStart: user.subscriptionStart,
      subscriptionEnd: user.subscriptionEnd
    });
  } catch (err) {
    console.error("❌ [/nita/check-and-activate] error:", err);
    return res.status(500).json({ message: "Erreur serveur lors du check/activation." });
  }
};



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













// const getCodesByBatch = async (req, res) => {
//   const { batchId } = req.params;

//   try {
//     const batch = await AccessCodeBatch.findOne({ batchId })
//       .populate("generatedBy", "fullName")
//       .populate("codes.usedBy", "fullName phone schoolName city");

//   //     const batch = await AccessCodeBatch.findOne({ batchId: req.params.batchId })
//   // .populate("codes.usedBy", "phone schoolName city");


//     if (!batch) {
//       return res.status(404).json({ message: "Lot introuvable." });
//     }

//    res.json(batch); // 👈 pour avoir tout le lot + les codes + utilisateurs

//   } catch (error) {
//     console.error("Erreur getCodesByBatch :", error);
//     res.status(500).json({ message: "Erreur lors du chargement du lot." });
//   }
// };






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

// const activateBatch = async (req, res) => {
//   try {
//     const { batchId } = req.body;

//     const batch = await AccessCodeBatch.findOne({ batchId });
//     if (!batch) {
//       return res.status(404).json({ message: "Lot introuvable." });
//     }

//     // Mise à jour des statuts uniquement si le code n’est pas utilisé
//     batch.codes = batch.codes.map(code =>
//       !code.used && code.status === "generated"
//         ? { ...code, status: "activated" }
//         : code
//     );

//     await batch.save();

//     res.json({ message: "✅ Tous les codes non utilisés ont été activés." });
//   } catch (error) {
//     console.error("Erreur lors de l’activation du lot :", error);
//     res.status(500).json({ message: "Erreur serveur lors de l’activation du lot." });
//   }
// };

const getCodesByBatch = async (req, res) => {
  const { batchId } = req.params;
  try {
    const batch = await AccessCodeBatch.findOne({ batchId })
      .populate("generatedBy", "fullName")
      .populate("codes.usedBy", "fullName phone schoolName city")
      .populate("codes.partner", "fullName phone"); // 👈 voir le partenaire

    if (!batch) return res.status(404).json({ message: "Lot introuvable." });
    res.json(batch);
  } catch (error) {
    console.error("Erreur getCodesByBatch :", error);
    res.status(500).json({ message: "Erreur lors du chargement du lot." });
  }
};


const activateBatch = async (req, res) => {
  try {
    const { batchId } = req.body;
    const now = new Date();

    const upd = await AccessCodeBatch.updateOne(
      { batchId },
      {
        $set: {
          'codes.$[c].status': 'activated',
          'codes.$[c].activatedAt': now
        }
      },
      { arrayFilters: [{ 'c.status': 'generated', 'c.used': { $ne: true } }] }
    );

    return res.json({
      message: "✅ Tous les codes non utilisés ont été activés.",
      modified: upd.modifiedCount
    });
  } catch (error) {
    console.error("Erreur lors de l’activation du lot :", error);
    res.status(500).json({ message: "Erreur serveur lors de l’activation du lot." });
  }
};



// const redeemCode = async (req, res) => {
//   const { code } = req.body;
//   const userId = req.user._id;

//   try {
//     const normalizedCode = code.trim().toUpperCase();

//     // 🔍 Trouver le lot contenant ce code
//     const batch = await AccessCodeBatch.findOne({
//       "codes.code": normalizedCode,
//     });

//     if (!batch) {
//       return res.status(404).json({ message: "❌ Code invalide ou inexistant." });
//     }

//     // 🔍 Trouver le code dans le lot
//     const targetCode = batch.codes.find((c) => c.code === normalizedCode);

//     if (!targetCode) {
//       return res.status(404).json({ message: "❌ Code introuvable." });
//     }

//     if (targetCode.used) {
//       return res.status(400).json({ message: "⚠️ Ce code a déjà été utilisé." });
//     }

//     // 🕐 Calcule la durée en fonction du type de lot
//     const now = new Date();
//     const durationInDays = batch.type === "annuel" ? 365 : 30;
//     const subscriptionEnd = new Date(now.getTime() + durationInDays * 24 * 60 * 60 * 1000);

//     // ✅ Mettre à jour l’utilisateur
//     await User.findByIdAndUpdate(userId, {
//       isSubscribed: true,
//       subscriptionStart: now,
//       subscriptionEnd: subscriptionEnd,
//       paymentReference: normalizedCode,
//     });

//     // ✅ Mettre à jour le code dans le lot
//     targetCode.used = true;
//     targetCode.status = "used"; // ou "activated" selon ta logique
//     targetCode.usedBy = userId;
//     targetCode.usedAt = now;

//     await batch.save();

//     res.status(200).json({ message: "✅ Code activé avec succès !" });
//   } catch (error) {
//     console.error("Erreur dans redeemCode :", error);
//     res.status(500).json({ message: "❌ Erreur serveur lors de la validation du code." });
//   }
// };

const redeemCode = async (req, res) => {
  const { code } = req.body;
  const userId = req.user._id;

  try {
    const normalizedCode = String(code || "").trim().toUpperCase();
    if (!normalizedCode) {
      return res.status(400).json({ message: "Code requis." });
    }

    // 🔍 Trouver le lot contenant ce code
    const batch = await AccessCodeBatch.findOne({ "codes.code": normalizedCode });
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

    // 🕐 Durée selon le lot
    const now = new Date();
    const durationInDays = batch.type === "annuel" ? 365 : 30;
    const subscriptionEnd = new Date(now.getTime() + durationInDays * 24 * 60 * 60 * 1000);

    // ✅ Mettre à jour l’utilisateur (et récupérer le n° pour le SMS)
    const user = await User.findByIdAndUpdate(
      userId,
      {
        isSubscribed: true,
        subscriptionStart: now,
        subscriptionEnd: subscriptionEnd,
        paymentReference: normalizedCode,
      },
      { new: true }
    );
    if (!user) return res.status(404).json({ message: "Utilisateur non trouvé." });

    // ✅ Marquer le code comme utilisé
    targetCode.used   = true;
    targetCode.status = "used";
    targetCode.usedBy = userId;
    targetCode.usedAt = now;
    await batch.save();

    // 🧾 Historique de paiement (recommandé)
    try {
      await PaymentHistory.create({
        user: user._id,
        phone: user.phone,
        amount: batch.price ?? (batch.type === "annuel" ? 20000 : 2000),
        reference: normalizedCode,
        paidAt: new Date()
      });
    } catch (e) {
      console.error("PaymentHistory (redeem) non enregistré :", e?.message);
    }

    // 📲 Envoi du SMS (non bloquant)
    const to  = phoneForSMS(user.phone);
    const end = subscriptionEnd.toISOString().slice(0, 10); // AAAA-MM-JJ
    const msg = `Fahimta: Votre abonnement par code ${normalizedCode} est actif jusqu'au ${end}. Merci !`;
    sendSMS(to, msg).catch(err => console.error("SMS redeemCode non envoyé:", err));

    // 📧 Envoi de l'email (si l'utilisateur a un email)
    if (user.email) {
      sendPaymentConfirmationEmail(user.email, {
        amount: batch.price ?? (batch.type === "annuel" ? 20000 : 2000),
        reference: normalizedCode,
        method: "Code",
        subscriptionEnd: subscriptionEnd,
        plan: batch.type === "annuel" ? "annuel" : "mensuel",
      }).catch(err => console.error("Email redeemCode non envoyé:", err));
    }

    return res.status(200).json({ message: "✅ Code activé avec succès !" });
  } catch (error) {
    console.error("Erreur dans redeemCode :", error);
    return res.status(500).json({ message: "❌ Erreur serveur lors de la validation du code." });
  }
};


// const activateSubscription = async (req, res) => {
//   try {
//     const userId = req.user._id;
//     const {
//       source = "NITA",
//       requestId,
//       reference,                 // ← on accepte la référence NITA
//       amount,
//       plan,
//       durationDays: durationOverride
//     } = req.body || {};

//     console.log("activateSubscription ←", { userId, source, requestId, reference, amount, plan });

//     if (!requestId && !reference) {
//       return res.status(400).json({ message: "requestId ou reference manquant." });
//     }

//     const refToStore = reference || requestId;

//     // Idempotence : si déjà activé pour cette référence
//     const already = await PaymentHistory.findOne({ user: userId, reference: refToStore });
//     if (already) {
//       const u = await User.findById(userId).select("isSubscribed subscriptionStart subscriptionEnd phone fullName");
//       return res.status(200).json({
//         message: "Abonnement déjà activé pour cette référence.",
//         subscriptionStart: u?.subscriptionStart,
//         subscriptionEnd: u?.subscriptionEnd
//       });
//     }

//     const user = await User.findById(userId);
//     if (!user) return res.status(404).json({ message: "Utilisateur non trouvé." });

//     // Durée
//     let days = Number(durationOverride);
//     if (!days || Number.isNaN(days) || days <= 0) {
//       const p = String(plan || "").toLowerCase();
//       if (p === "annuel") days = 365;
//       else if (Number(amount) >= 15000) days = 365;
//       else days = 30; // défaut: mensuel
//     }

//     // Montant à enregistrer
//     const amountVal = Number(amount) || (String(plan).toLowerCase() === 'annuel' ? 20000 : 2000);

//     const now = new Date();
//     const base = (user.subscriptionEnd && user.subscriptionEnd > now) ? user.subscriptionEnd : now;
//     const newEnd = new Date(base.getTime() + days * 24 * 60 * 60 * 1000);

//     // Mise à jour utilisateur
//     user.isSubscribed = true;
//     if (!user.subscriptionStart) user.subscriptionStart = now; // n’écrase pas si l’utilisateur avait déjà un historique
//     user.subscriptionEnd = newEnd;
//     user.paymentReference = refToStore;
//     await user.save();

//     // Historique paiement
//     await PaymentHistory.create({
//       user: user._id,
//       phone: user.phone,
//       amount: amountVal,
//       reference: refToStore,
//       paidAt: new Date()
//     });

//     console.log('activateSubscription ←', { userId, source, requestId, reference, amount, plan });

//   // Après calcul des dates
//  console.log('activateSubscription → newEnd', newEnd.toISOString());

//     // Envoi SMS (non bloquant)
//     try {
//       const to = phoneForSMS(user.phone);
//       const msg = `Fahimta: Votre abonnement est actif jusqu'au ${newEnd.toISOString().slice(0,10)}. Merci!`;
//       sendSMS(to, msg).catch(err => console.error("SMS non envoyé:", err));
//     } catch (e) {
//       console.error("SMS exception:", e?.message);
//     }

//     return res.status(200).json({
//       message: "✅ Abonnement activé avec succès.",
//       subscriptionStart: user.subscriptionStart,
//       subscriptionEnd: user.subscriptionEnd
//     });
//   } catch (err) {
//     console.error("❌ Erreur activateSubscription :", err);
//     return res.status(500).json({ message: "Erreur serveur lors de l'activation." });
//   }
// };

// controllers/paymentController.js

const activateSubscription = async (req, res) => {
  console.log('➡️  [activateSubscription] start');

  try {
    const userId = req.user?._id;
    const {
      source = "NITA",
      requestId,
      reference,                 // référence/code NITA
      amount,
      plan,
      durationDays: durationOverride
    } = req.body || {};

    console.log('🟡 Input =', {
      userId: userId?.toString?.(),
      source, requestId, reference, amount, plan, durationOverride
    });

    if (!requestId && !reference) {
      console.log('🔴 Missing: requestId/reference');
      return res.status(400).json({ message: "requestId ou reference manquant." });
    }

    const refToStore = reference || requestId;

    // Idempotence
    const already = await PaymentHistory.findOne({ user: userId, reference: refToStore }).lean();
    if (already) {
      console.log('🟠 Déjà activé pour ref =', refToStore, ' → phId =', already._id?.toString());
      const u = await User.findById(userId).select("isSubscribed subscriptionStart subscriptionEnd").lean();
      return res.status(200).json({
        message: "Abonnement déjà activé pour cette référence.",
        subscriptionStart: u?.subscriptionStart,
        subscriptionEnd: u?.subscriptionEnd
      });
    }

    const user = await User.findById(userId);
    if (!user) {
      console.log('🔴 Utilisateur introuvable:', userId?.toString?.());
      return res.status(404).json({ message: "Utilisateur non trouvé." });
    }

    // Durée
    let days = Number(durationOverride);
    if (!days || Number.isNaN(days) || days <= 0) {
      const p = String(plan || "").toLowerCase();
      days = (p === "annuel" || Number(amount) >= 15000) ? 365 : 30;
    }
    console.log('🧮 Durée retenue (jours) =', days);

    // Montant
    const amountVal = Number(amount) || (String(plan).toLowerCase() === 'annuel' ? 20000 : 2000);

    // Dates
    const now = new Date();
    const base = (user.subscriptionEnd && user.subscriptionEnd > now) ? user.subscriptionEnd : now;
    const newEnd = new Date(base.getTime() + days * 24 * 60 * 60 * 1000);
    console.log('⏱  base =', base.toISOString(), '→ newEnd =', newEnd.toISOString());

    // MAJ utilisateur
    user.isSubscribed = true;
    if (!user.subscriptionStart) user.subscriptionStart = now; // n’écrase pas un historique
    user.subscriptionEnd = newEnd;
    user.paymentReference = refToStore;
    await user.save();
    console.log('✅ User maj →', {
      userId: user._id?.toString?.(),
      isSubscribed: user.isSubscribed,
      subscriptionStart: user.subscriptionStart?.toISOString?.(),
      subscriptionEnd: user.subscriptionEnd?.toISOString?.(),
      paymentReference: user.paymentReference
    });

    // Historique paiement
    let ph;
    try {
      ph = await PaymentHistory.create({
        user: user._id,
        phone: user.phone,
        amount: amountVal,
        reference: refToStore,
        paidAt: new Date()
      });
      console.log('🧾 PaymentHistory créé →', {
        id: ph._id?.toString?.(),
        amount: amountVal,
        reference: refToStore
      });
    } catch (e) {
      console.error('⚠️ PaymentHistory create error:', e?.message);
    }

    // SMS (non bloquant)
    try {
      const to = phoneForSMS(user.phone);
      const msg = `Fahimta: Votre abonnement est actif jusqu'au ${newEnd.toISOString().slice(0,10)}. Merci!`;
      const smsRes = await sendSMS(to, msg);
      console.log('📲 sendSMS →', smsRes);
    } catch (e) {
      console.error('⚠️ SMS error:', e?.message);
    }

    // Email (si l'utilisateur a un email)
    if (user.email) {
      try {
        const p = String(plan || "").toLowerCase();
        const emailRes = await sendPaymentConfirmationEmail(user.email, {
          amount: amountVal,
          reference: refToStore,
          method: source === "NITA" ? "NITA" : "Carte",
          subscriptionEnd: newEnd,
          plan: p === "annuel" || amountVal >= 15000 ? "annuel" : "mensuel",
        });
        console.log('📧 sendPaymentConfirmationEmail →', emailRes);
      } catch (e) {
        console.error('⚠️ Email error:', e?.message);
      }
    }

    console.log('🏁 [activateSubscription] done OK for', user._id?.toString?.());
    return res.status(200).json({
      message: "✅ Abonnement activé avec succès.",
      subscriptionStart: user.subscriptionStart,
      subscriptionEnd: user.subscriptionEnd
    });
  } catch (err) {
    console.error('❌ [activateSubscription] error:', err);
    return res.status(500).json({ message: "Erreur serveur lors de l'activation." });
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



// const nitaCallbackPublic = async (req, res) => {
//   try {

//       console.log('🔔 NITA CALLBACK HEADERS =', req.headers);
//     console.log('🔔 NITA CALLBACK QUERY   =', req.query);
//     console.log('🔔 NITA CALLBACK BODY    =', req.body);
//     console.log('📥 NITA CALLBACK BODY =', req.body);
//     const {
//       requestId,
//       referenceAchat,
//       status,
//       statusTransaction,
//       code, // parfois
//       phoneClient,
//       montant
//     } = req.body || {};

//     const raw = String(status || code || statusTransaction || '').toLowerCase();
//     const isPaid = ['1','success','succès','ok','paid'].includes(raw);
//     if (!isPaid) return res.status(200).send('IGNORED');

//     // retrouver l’utilisateur par téléphone
//     const normalize = (s='') => {
//       s = String(s).replace(/\s+/g,'');
//       if (s.startsWith('+')) s = s.slice(1);
//       if (s.startsWith('00')) s = s.slice(2);
//       if (/^\d{8}$/.test(s)) s = '227' + s;
//       return s; // "227XXXXXXXX"
//     };
//     const p = normalize(phoneClient);
//     const user = await User.findOne({
//       $or: [
//         { phone: p },
//         { phone: '+' + p },
//         { phone: '00' + p }
//       ]
//     });
//     if (!user) return res.status(200).send('USER_NOT_FOUND');

//     // activer l’abonnement (30 jours par défaut)
//     const now = new Date();
//     const base = (user.subscriptionEnd && user.subscriptionEnd > now) ? user.subscriptionEnd : now;
//     const newEnd = new Date(base.getTime() + 30*24*60*60*1000);
//     user.isSubscribed = true;
//     if (!user.subscriptionStart) user.subscriptionStart = now;
//     user.subscriptionEnd = newEnd;
//     user.paymentReference = referenceAchat || requestId;
//     await user.save();

//     await PaymentHistory.create({
//       user: user._id,
//       phone: user.phone,
//       amount: Number(montant) || 2000,
//       reference: referenceAchat || requestId,
//       paidAt: new Date()
//     });

//     const to = p; // déjà "227XXXXXXXX"
//     const msg = `Fahimta: Votre abonnement est actif jusqu'au ${newEnd.toISOString().slice(0,10)}. Merci!`;
//     sendSMS(to, msg).catch(e => console.error('SMS callback non envoyé:', e));

//     return res.status(200).send('OK');
//   } catch (e) {
//     console.error('❌ NITA callback error:', e);
//     return res.status(500).send('ERR');
//   }
// };



const nitaCallbackPublic = async (req, res) => {
  try {
    console.log('🔔 NITA CALLBACK METHOD =', req.method);
    console.log('🔔 NITA CALLBACK HEADERS =', req.headers);
    console.log('🔔 NITA CALLBACK QUERY   =', req.query);
    console.log('🔔 NITA CALLBACK BODY    =', req.body);

    // fusionne tout ce qu'on peut recevoir (GET/POST)
    const bag = { ...(req.query||{}), ...(req.body||{}) };

    // NITA envoie souvent: status, transaction_id
    const statusRaw = String(bag.status ?? bag.code ?? bag.statusTransaction ?? '').trim().toLowerCase();
    const isPaid = ['1','ok','success','succès','paid'].includes(statusRaw);
    if (!isPaid) {
      console.log('ℹ️ Callback non payé →', statusRaw);
      return res.status(200).send('IGNORED');
    }

    const reference = bag.referenceAchat || bag.transaction_id || bag.codeAchat || bag.ref || bag.reference;
    const reqId     = bag.requestId || bag.req || bag.rid;
    const normalize = (s='') => {
      s = String(s).replace(/\s+/g,'');
      if (s.startsWith('+')) s = s.slice(1);
      if (s.startsWith('00')) s = s.slice(2);
      if (/^\d{8}$/.test(s)) s = '227' + s;
      return s; // 227XXXXXXXX
    };
    const phoneNorm = normalize(bag.phone || bag.phoneClient);

    // ➜ On doit pouvoir identifier l'utilisateur (via phone passé en query)
    if (!phoneNorm) {
      console.log('⚠️ Callback sans téléphone. Ajoute &phone=00227XXXXXXX dans urlCallback.');
      return res.status(200).send('MISSING_PHONE');
    }

    const user = await User.findOne({
      $or: [{ phone: phoneNorm }, { phone: '+'+phoneNorm }, { phone: '00'+phoneNorm }]
    });
    if (!user) {
      console.log('⚠️ USER_NOT_FOUND pour phone=', phoneNorm);
      return res.status(200).send('USER_NOT_FOUND');
    }

    // Active 30 jours (mensuel)
    const now = new Date();
    const base = (user.subscriptionEnd && user.subscriptionEnd > now) ? user.subscriptionEnd : now;
    const newEnd = new Date(base.getTime() + 30*24*60*60*1000);

    user.isSubscribed = true;
    if (!user.subscriptionStart) user.subscriptionStart = now;
    user.subscriptionEnd = newEnd;
    user.paymentReference = reference || reqId || 'NITA';
    await user.save();

    await PaymentHistory.create({
      user: user._id,
      phone: user.phone,
      amount: Number(bag.montant) || 2000,
      reference: reference || reqId || 'NITA',
      paidAt: new Date()
    });

    const msg = `Fahimta: Votre abonnement est actif jusqu'au ${newEnd.toISOString().slice(0,10)}. Merci!`;
    sendSMS(phoneNorm, msg).catch(e => console.error('SMS callback non envoyé:', e));

    // Email (si l'utilisateur a un email)
    if (user.email) {
      sendPaymentConfirmationEmail(user.email, {
        amount: Number(bag.montant) || 2000,
        reference: reference || reqId || 'NITA',
        method: "NITA",
        subscriptionEnd: newEnd,
        plan: "mensuel",
      }).catch(e => console.error('Email callback non envoyé:', e));
    }

    console.log('✅ Abonnement activé via callback', { phone: user.phone, ref: reference || reqId });
    return res.status(200).send('OK');
  } catch (e) {
    console.error('❌ NITA callback error:', e);
    return res.status(500).send('ERR');
  }
};


// POST /api/payments/assign-codes  { batchId, partnerId, count }
const assignCodesToPartner = async (req, res) => {
  try {
    const { batchId, partnerId, count } = req.body;
    if (!batchId || !partnerId) {
      return res.status(400).json({ message: "batchId et partnerId requis." });
    }

    // sécurité : le partnerId doit bien correspondre à un user role=partner
    const partner = await User.findById(partnerId).select("role fullName");
    if (!partner || partner.role !== "partner") {
      return res.status(400).json({ message: "partnerId invalide (rôle partner requis)." });
    }

    const batch = await AccessCodeBatch.findOne({ batchId });
    if (!batch) return res.status(404).json({ message: "Lot introuvable." });

    const now = new Date();
    const indicesEligibles = [];
    batch.codes.forEach((c, i) => {
      if (!c.used && !c.partner) indicesEligibles.push(i);
    });

    const take = Math.min(Number(count || indicesEligibles.length), indicesEligibles.length);
    for (let i = 0; i < take; i++) {
      const k = indicesEligibles[i];
      batch.codes[k].partner = partnerId;
      batch.codes[k].assignedAt = now;
    }
    await batch.save();

    return res.json({ message: "Assignation effectuée.", assignedCount: take });
  } catch (e) {
    console.error("assignCodesToPartner error:", e);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// GET /api/payments/partners/my-codes?status=all|generated|activated|used
// GET /api/payments/partners/my-codes?status=all|generated|activated|used
const getMyPartnerCodes = async (req, res) => {
  try {
    const partnerId = req.user._id;
    const status = String(req.query.status || "activated").toLowerCase();

    let matchStatus = {};
    if (status === "available") {
      // Disponibles = activées mais pas vendues ni utilisées
      matchStatus = { 
        "codes.status": "activated"
      };
    } else if (status !== "all") {
      matchStatus = { "codes.status": status };
    }

    const items = await AccessCodeBatch.aggregate([
      { $match: { "codes.partner": partnerId } },
      { $unwind: "$codes" },
      { $match: { "codes.partner": partnerId, ...matchStatus } },
      {
        $project: {
          _id: "$codes._id",
          batchId: "$batchId",
          type: "$type",
          faceValueCfa: { $ifNull: ["$codes.price", "$price"] },
          codeRaw: "$codes.code",
          status: "$codes.status",
          assignedAt: "$codes.assignedAt",
          activatedAt: "$codes.activatedAt",
          soldAt: "$codes.soldAt",
          usedAt: "$codes.usedAt",
          commissionCfa: { $ifNull: ["$codes.commissionCfa", 0] },
        }
      },
      { $sort: { assignedAt: -1, activatedAt: -1, soldAt: -1, usedAt: -1 } }
    ]);

    // masque mais garde le code et l'_id
    const secured = items.map(i => ({
      ...i,
      code: i.codeRaw,
      codeMasked: maskCode(i.codeRaw || "")
    })).map(i => { delete i.codeRaw; return i; });

    return res.json({ count: secured.length, items: secured });
  } catch (e) {
    console.error("getMyPartnerCodes error:", e);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// GET /api/payments/partners/my-stats
const getMyPartnerStats = async (req, res) => {
  try {
    const partnerId = req.user._id.toString();
    const batches = await AccessCodeBatch.find({ "codes.partner": partnerId }).select("codes");

    let assigned = 0, activated = 0, sold = 0, used = 0, commissionCfa = 0;
    for (const b of batches) {
      for (const c of b.codes) {
        if (String(c.partner) !== partnerId) continue;
        assigned += 1;
        if (c.status === "activated") activated += 1;
        if (c.soldAt) sold += 1;
        if (c.status === "used") used += 1;
        commissionCfa += Number(c.commissionCfa || 0);
      }
    }
    return res.json({ assigned, activated, sold, used, commissionCfa });
  } catch (e) {
    console.error("getMyPartnerStats error:", e);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// PATCH /api/payments/partners/mark-sold  { code, commissionCfa }
const partnerMarkSold = async (req, res) => {
  try {
    const { code, commissionCfa } = req.body;
    if (!code) return res.status(400).json({ message: "code requis." });

    const normalized = String(code).trim().toUpperCase();

    // sécurité : seul le partenaire propriétaire du code peut le marquer vendu
    const upd = await AccessCodeBatch.updateOne(
      { "codes.code": normalized, "codes.partner": req.user._id },
      {
        $set: {
          "codes.$.soldAt": new Date(),
          "codes.$.commissionCfa": Number(commissionCfa || 0)
        }
      }
    );

    if (upd.matchedCount === 0) {
      return res.status(404).json({ message: "Code introuvable ou non assigné à ce partenaire." });
    }
    return res.json({ message: "Marqué comme vendu." });
  } catch (e) {
    console.error("partnerMarkSold error:", e);
    res.status(500).json({ message: "Erreur serveur." });
  }
};



// utilise tes ENV déjà en place
const nitaCreateAchatServer = async (req, res) => {
  try {
    const { amount, label } = req.body || {};
    const user = req.user;
    if (!user) return res.status(401).json({ message: "Unauthenticated" });

    const reqId = (String(label||'').toLowerCase().includes('mensuel') ? 'FAH-M-' : 'FAH-A-') + Date.now();

    // 1) Auth NITA
    const rAuth = await axios.post(
      `${NITA_BASE_URL}/api/authenticate`,
      { username: NITA_USERNAME, password: NITA_PASSWORD },
      { headers: { "Content-Type":"application/json", "X-NT-API-KEY": NITA_API_KEY, Accept:"application/json" } }
    );
    const dAuth = rAuth.data || {};
    const jwt = dAuth.token || dAuth.access_token || dAuth.jwt || dAuth?.data?.token;
    if (!jwt) return res.status(500).json({ message: "Auth NITA failed" });

    // helpers
    const phoneToNita = (raw="")=>{
      let s = String(raw).replace(/\s+/g,"");
      if (s.startsWith("+")) s = "00"+s.slice(1);
      if (s.startsWith("227")) s = "00"+s;
      if (/^\d{8}$/.test(s)) s = "00227"+s;
      return s;
    };
    const phoneForCallback = (raw="")=>{
      let s = String(raw).replace(/\s+/g,"");
      if (s.startsWith("+")) s = s.slice(1);
      if (s.startsWith("00")) s = s.slice(2);
      if (/^0\d{8}$/.test(s)) s = s.slice(1);
      if (/^\d{8}$/.test(s)) s = "227"+s;
      return s;
    };

    // URL publique de ton API (déjà déployée Heroku)
    const PUBLIC_API_BASE = process.env.PUBLIC_API_BASE || "https://fahimtabackend-647bfe306335.herokuapp.com/api";
    const urlCallback = `${PUBLIC_API_BASE}/payments/nita/callback?phone=${encodeURIComponent(phoneForCallback(user.phone))}&requestId=${encodeURIComponent(reqId)}`;

    const payload = {
      descriptionAchat: [label],
      montantTransaction: amount,
      motifTransaction: label,
      requestId: reqId,
      adresseIp: "102.45.67.89",
      phoneClient: phoneToNita(user.phone),
      urlCallback,
    };

    const rSave = await axios.post(
      `${NITA_BASE_URL}/api/nitaServices/achatEnLigne/saveAchatEnLigne`,
      payload,
      { headers: { "Content-Type":"application/json", "X-NT-API-KEY": NITA_API_KEY, "Authorization": `Bearer ${jwt}`, Accept:"application/json" } }
    );

    const data = rSave.data || {};
    if (Number(data?.code) !== 200) {
      return res.status(400).json({ message: data?.message || "Erreur NITA" });
    }

    const reference =
      data.referenceAchat || data.codeAchat || data.reference || data.ref ||
      data?.data?.referenceAchat || data?.data?.codeAchat ||
      data?.achat?.referenceAchat || data?.result?.referenceAchat || null;

    if (!reference) return res.status(500).json({ message: "Référence introuvable." });

    return res.json({ reference, reqId });
  } catch (e) {
    console.error("nitaCreateAchatServer error:", e?.response?.data || e?.message);
    return res.status(500).json({ message: "Erreur serveur NITA." });
  }
};










module.exports = { simulatePayment, getAccessCodeStats, activateBatch , redeemCode, generateCodes, getAllAccessCodes, getCodesByBatch, activateSubscription, nitaCallbackPublic, 
  checkNitaAndActivate ,

  // 🔻 Partenaires
  assignCodesToPartner,
  getMyPartnerCodes,
  getMyPartnerStats,
  partnerMarkSold,
    nitaCreateAchatServer,
};
