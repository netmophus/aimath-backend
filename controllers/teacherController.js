const SupportRequest = require("../models/SupportRequest");
const User = require("../models/userModel");
const Message = require("../models/Message");
const MessageHistory = require("../models/MessageHistory");

const Teacher = require("../models/Teacher"); // assure-toi que c'est bien importé tout en haut
const TeacherPayout = require("../models/TeacherPayout");


// ADD — règles simples
const PTS_PER_REQ = Number(process.env.PTS_PER_REQ || 1);          // 1 point par requête
const PAY_PER_REQ_CFA = Number(process.env.PAY_PER_REQ_CFA || 20); // 20 FCFA par point

// ADD — calcul du montant (pas de seuil/plafond)
const computePayout = (points) => Math.floor(points) * PAY_PER_REQ_CFA;





exports.updateTeacherProfile = async (req, res) => {
  try {
    const teacher = await Teacher.findOne({ userId: req.user._id });
    if (!teacher) {
      return res.status(404).json({ message: "Enseignant non trouvé." });
    }

    const { subjects, levels, level, experience, gpsLocation } = req.body;

    if (subjects) teacher.subjects = subjects;
    if (levels) teacher.levels = levels;
    if (level) teacher.level = level;
    if (experience) teacher.experience = experience;
    if (gpsLocation) teacher.gpsLocation = gpsLocation;

    await teacher.save();

    res.status(200).json({ message: "Profil enseignant mis à jour avec succès." });
  } catch (error) {
    console.error("❌ Erreur mise à jour profil enseignant :", error);
    res.status(500).json({ message: "Erreur serveur lors de la mise à jour." });
  }
};


exports.getSupportRequestsForTeacher = async (req, res) => {
  try {
    const teacherId = req.user._id;

    // Afficher :
    // 1️⃣ Toutes les demandes NON encore attribuées (teacher: null)
    // 2️⃣ Et celles déjà attribuées à CET enseignant
    const requests = await SupportRequest.find({
      $or: [
        { teacher: null },
        { teacher: teacherId }
      ]
    })
      .populate("student", "fullName schoolName city")
      .sort({ createdAt: -1 });

    res.json(requests);
  } catch (error) {
    console.error("❌ Erreur récupération demandes enseignant:", error);
    res.status(500).json({ message: "Erreur serveur lors de la récupération des demandes." });
  }
};





exports.updateSupportRequestStatus = async (req, res) => {
  try {
    const requestId = req.params.id;
    const { status } = req.body;

    const allowedStatuses = ["en_attente", "acceptee", "refusee", "terminee"];
    if (!allowedStatuses.includes(status)) {
      return res.status(400).json({ message: "Statut invalide." });
    }

    const request = await SupportRequest.findById(requestId);

    if (!request) {
      return res.status(404).json({ message: "Demande non trouvée." });
    }

    if (request.status === "terminee") {
      return res.status(403).json({ message: "Cette demande est déjà terminée." });
    }

    // ✅ Attribution de l’enseignant si besoin
    if (!request.teacher) {
      request.teacher = req.user._id;
    } else if (request.teacher.toString() !== req.user._id.toString()) {
      return res.status(403).json({ message: "Cette demande est déjà assignée à un autre enseignant." });
    }

    // ✅ Si le statut devient "terminee", archiver les messages
    if (status === "terminee") {
      const messages = await Message.find({
        $or: [
          { from: request.student, to: request.teacher },
          { from: request.teacher, to: request.student }
        ]
      });

      const historyDocs = messages.map((msg) => ({
        from: msg.from,
        to: msg.to,
        text: msg.text,
        fileUrl: msg.fileUrl,
        fileType: msg.fileType,
        isVoiceMessage: msg.isVoiceMessage,
        read: msg.read,
        createdAt: msg.createdAt,
        originalRequest: request._id,
      }));

      if (historyDocs.length > 0) {
        await MessageHistory.insertMany(historyDocs);
        await Message.deleteMany({
          _id: { $in: messages.map((m) => m._id) }
        });
      }

      request.sessionStarted = false; // Fin de session


// ▼▼▼ AJOUT ICI: figer la demande pour la paie
const now = new Date();
request.completedAt     = now;
request.awardedPoints   = PTS_PER_REQ;                     // ex: 10
request.payoutMonth     = now.toISOString().slice(0, 7);   // "YYYY-MM"
request.countedForPayout = true;                           // marqué comme comptabilisé




    }


    // marquage pour la rémunération (idempotent)
if (!request.completedAt) request.completedAt = new Date();
if (!request.payoutMonth) request.payoutMonth = new Date().toISOString().slice(0, 7);
if (!request.awardedPoints || request.awardedPoints <= 0) request.awardedPoints = 1;


    if (status === "acceptee") {
      request.sessionStarted = true;
    }

    request.status = status;
    await request.save();


    // ─── AJOUT: si la demande vient d'être terminée, upsert le cumul mensuel ───
// if (status === "terminee") {
//   try {
//     // sécurité minimale: il doit y avoir un enseignant et des points à incrémenter
//     if (!request.teacher) {
//       console.warn("[PAYOUT] Request terminée sans teacher:", request._id.toString());
//     } else if (!request.awardedPoints || !request.payoutMonth) {
//       console.warn("[PAYOUT] Request terminée sans awardedPoints/payoutMonth:", request._id.toString());
//     } else {
//       // upsert cumul mensuel (points + compteur)
//       const tp = await TeacherPayout.findOneAndUpdate(
//         { teacher: request.teacher, month: request.payoutMonth },
//         {
//           $inc: { points: request.awardedPoints, requestsCount: 1 },
//           $setOnInsert: { capCfa: PAYOUT_CAP }
//         },
//         { new: true, upsert: true }
//       );

//       // recalcul du montant à verser (proportionnel jusqu'au plafond)
//       const newPayout = computePayout(tp.points, PTS_THRESHOLD, PAYOUT_CAP);
//       if (tp.payoutCfa !== newPayout) {
//         tp.payoutCfa = newPayout;
//         await tp.save();
//       }

//       console.log("[PAYOUT] Upsert OK →", {
//         teacher: tp.teacher?.toString?.(),
//         month: tp.month,
//         points: tp.points,
//         requestsCount: tp.requestsCount,
//         payoutCfa: tp.payoutCfa
//       });
//     }
//   } catch (e) {
//     console.error("❌ [PAYOUT] Upsert error:", e?.message);
//   }
// }


if (status === "terminee") {
  try {
    if (!request.teacher) {
      console.warn("[PAYOUT] Request terminée sans teacher:", request._id.toString());
    } else if (!request.awardedPoints || !request.payoutMonth) {
      console.warn("[PAYOUT] Request terminée sans awardedPoints/payoutMonth:", request._id.toString());
    } else {
      const tp = await TeacherPayout.findOneAndUpdate(
        { teacher: request.teacher, month: request.payoutMonth },
        { $inc: { points: request.awardedPoints, requestsCount: 1 } },
        { new: true, upsert: true }
      );

      const newPayout = computePayout(tp.points); // ← simple: points * 20 FCFA
      if (tp.payoutCfa !== newPayout) {
        tp.payoutCfa = newPayout;
        await tp.save();
      }

      console.log("[PAYOUT] Upsert OK →", {
        teacher: tp.teacher?.toString?.(),
        month: tp.month,
        points: tp.points,
        requestsCount: tp.requestsCount,
        payoutCfa: tp.payoutCfa
      });
    }
  } catch (e) {
    console.error("❌ [PAYOUT] Upsert error:", e?.message);
  }
}




    // ✅ Populate juste avant envoi
const populatedRequest = await SupportRequest.findById(request._id).populate("student", "fullName schoolName city");

res.status(200).json(populatedRequest);

    // res.status(200).json(request);
  } catch (error) {
    console.error("❌ Erreur mise à jour statut :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};











exports.startSessionForRequest = async (req, res) => {
  try {
    const { id } = req.params;
    const teacherId = req.user._id;

    const request = await SupportRequest.findById(id);

    if (!request) {
      return res.status(404).json({ message: "Demande introuvable." });
    }

    if (request.teacher.toString() !== teacherId.toString()) {
      return res.status(403).json({ message: "Non autorisé." });
    }

    if (request.sessionStarted) {
      return res.status(400).json({ message: "La session a déjà commencé." });
    }

    request.sessionStarted = true;
    await request.save();

    res.json({ message: "Session démarrée avec succès." });
  } catch (error) {
    console.error("❌ Erreur démarrage session :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};



// ✅ Obtenir les infos de l’enseignant connecté
exports.getCurrentTeacher = async (req, res) => {
  try {
    const user = await User.findById(req.user._id).select("fullName _id");
    res.status(200).json(user);
  } catch (error) {
    console.error("❌ Erreur récupération enseignant :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};




// 📸 Mettre à jour la photo de profil
exports.updateTeacherPhoto = async (req, res) => {
  try {
    const user = await User.findById(req.user._id); // pas Teacher
    if (!user) {
      return res.status(404).json({ message: "Utilisateur non trouvé" });
    }

    user.photo = req.body.photo; // Injectée par Cloudinary
    await user.save();

    res.status(200).json({ message: "Photo mise à jour avec succès", photo: user.photo });
  } catch (err) {
    console.error("Erreur mise à jour photo enseignant :", err);
    res.status(500).json({ message: "Erreur serveur" });
  }
};





/* Utilitaire : formatage téléphone -> +227XXXXXXXX */
const formatPhone = (input = "") => {
  const digits = String(input).replace(/\D/g, "");
  if (!digits) return null;
  return digits.startsWith("227") ? `+${digits}` : `+227${digits}`;
};




/* ===========================
   ADMIN: liste des enseignants
   GET /api/admin/teachers
=========================== */
exports.adminListTeachers = async (req, res) => {
  try {
    const teachers = await User.find({ role: "teacher" })
      .select("fullName phone schoolName city isActive isVerified profileCompleted photo createdAt")
      .sort({ createdAt: -1 });

    return res.json(teachers);
  } catch (err) {
    console.error("adminListTeachers error:", err);
    return res.status(500).json({ message: "Erreur serveur lors du listing des enseignants." });
  }
};

/* ===========================
   ADMIN: créer un enseignant (sans OTP)
   POST /api/admin/teachers
   body: { fullName, phone, password, schoolName, city }
=========================== */
exports.adminCreateTeacher = async (req, res) => {
  try {
    const { fullName, phone, password, schoolName, city } = req.body;

    if (!fullName || !phone || !password || !schoolName || !city) {
      return res.status(400).json({ message: "Nom, téléphone, mot de passe, école et ville sont obligatoires." });
    }

    const formattedPhone = formatPhone(phone);
    if (!formattedPhone || formattedPhone.length < 12) {
      return res.status(400).json({ message: "Téléphone invalide." });
    }

    const exists = await User.findOne({ phone: formattedPhone });
    if (exists) {
      return res.status(400).json({ message: "Un compte existe déjà avec ce téléphone." });
    }

    // Création SANS OTP
    const user = new User({
      role: "teacher",
      fullName,
      phone: formattedPhone,
      password,
      schoolName,
      city,
      provider: "local",
      isVerified: true,         // pas d’OTP
      isActive: true,
      profileCompleted: false,
    });

    // Le modèle vérifie passwordConfirm en pre('validate'), on le renseigne donc :
    user.passwordConfirm = password;

    await user.save();

    return res.status(201).json({
      message: "✅ Enseignant créé avec succès.",
      teacher: {
        _id: user._id,
        fullName: user.fullName,
        phone: user.phone,
        schoolName: user.schoolName,
        city: user.city,
        isActive: user.isActive,
        isVerified: user.isVerified,
        createdAt: user.createdAt,
      },
    });
  } catch (err) {
    console.error("adminCreateTeacher error:", err);
    return res.status(500).json({ message: "Erreur serveur lors de la création de l'enseignant." });
  }
};

/* ===========================
   ADMIN: activer/désactiver un enseignant
   PATCH /api/admin/teachers/:id/toggle
=========================== */
exports.adminToggleTeacherActive = async (req, res) => {
  try {
    const { id } = req.params;
    const teacher = await User.findById(id);

    if (!teacher || teacher.role !== "teacher") {
      return res.status(404).json({ message: "Enseignant introuvable." });
    }

    teacher.isActive = !teacher.isActive;
    await teacher.save();

    return res.json({
      message: `Enseignant ${teacher.isActive ? "activé" : "désactivé"} avec succès.`,
      isActive: teacher.isActive,
    });
  } catch (err) {
    console.error("adminToggleTeacherActive error:", err);
    return res.status(500).json({ message: "Erreur serveur lors de la mise à jour du statut." });
  }
};

/* ===========================
   ADMIN: supprimer un enseignant
   DELETE /api/admin/teachers/:id
=========================== */
exports.adminDeleteTeacher = async (req, res) => {
  try {
    const { id } = req.params;

    const teacher = await User.findById(id);
    if (!teacher || teacher.role !== "teacher") {
      return res.status(404).json({ message: "Enseignant introuvable." });
    }

    await User.findByIdAndDelete(id);
    return res.json({ message: "🗑️ Enseignant supprimé avec succès." });
  } catch (err) {
    console.error("adminDeleteTeacher error:", err);
    return res.status(500).json({ message: "Erreur serveur lors de la suppression." });
  }
};




// ───────────────────────────────────────────────────────────
//  Historique des demandes acceptées/terminées (enseignant)
// GET /api/teachers/support-requests/history
// ───────────────────────────────────────────────────────────
exports.getAcceptedHistory = async (req, res) => {
  try {
    const teacherId = req.user._id;

    const requests = await SupportRequest.find({
      teacher: teacherId,
      status: { $in: ["acceptee", "terminee"] },
    })
      .populate("student", "fullName schoolName city")
      .sort({ updatedAt: -1 });

    return res.json(requests);
  } catch (err) {
    console.error("getAcceptedHistory error:", err);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};

// ───────────────────────────────────────────────────────────
//  Résumé de points / paiement du mois (enseignant)
// GET /api/teachers/payout/me?month=YYYY-MM
// ───────────────────────────────────────────────────────────
// GET /api/teachers/payout/me?month=YYYY-MM
exports.getMyPayoutSummary = async (req, res) => {
  try {
    const teacherId = req.user._id;
    const month = (req.query.month || new Date().toISOString().slice(0, 7)).slice(0, 7); // "YYYY-MM"

    const start = new Date(`${month}-01T00:00:00.000Z`);
    const end = new Date(start);
    end.setUTCMonth(end.getUTCMonth() + 1);

    const RATE = Number(process.env.REWARD_PER_POINT || 80); // FCFA / point

    const finished = await SupportRequest.find({
      teacher: teacherId,
      status: "terminee",
      completedAt: { $gte: start, $lt: end },
    }).select("awardedPoints");

    const totalRequests = finished.length;
    const totalPoints = finished.reduce((s, r) => s + (Number(r.awardedPoints) || 1), 0);
    const amountCfa = totalPoints * RATE;

    return res.json({
      month,
      totalRequests,
      totalPoints,
      rateCfaPerPoint: RATE,
      amountCfa,
    });
  } catch (err) {
    console.error("getMyPayoutSummary error:", err);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};

