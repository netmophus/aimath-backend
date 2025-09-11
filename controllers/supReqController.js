const SupportRequest = require("../models/SupportRequest");
const User = require("../models/userModel");

// ✅ 1. Créer une demande de soutien

const MonthlyUsage = require("../models/MonthlyUsage");

// utilitaire période courante "YYYY-MM"
const currentPeriod = () => new Date().toISOString().slice(0, 7);

// limite par mois
const REQUESTS_PER_MONTH = 2;

// Assure-toi d'avoir ces helpers/constantes en haut du fichier (ou import depuis config/usage)

exports.createSupportRequest = async (req, res) => {
  try {
    const { topic, type, level, description, serie } = req.body;

    // ✅ Validation minimale
    if (!topic || !type || !level) {
      return res.status(400).json({ message: "Les champs obligatoires sont manquants." });
    }

    // 🔒 Uniquement 1 demande en cours par élève
    const existingRequest = await SupportRequest.findOne({
      student: req.user._id,
      status: { $in: ["en_attente", "acceptee"] },
    });
    if (existingRequest) {
      return res.status(400).json({
        message:
          "Vous avez déjà une demande de soutien en cours. Veuillez la terminer avant d’en créer une nouvelle.",
      });
    }

    // ✅ QUOTA mensuel (atomic + rollback en cas d'échec)
    const period = currentPeriod();
    let usage;

    try {
      // Atomic upsert + increment
      usage = await MonthlyUsage.findOneAndUpdate(
        { user: req.user._id, period },
        {
          $inc: { supportRequestsCreated: 1 },
          $setOnInsert: {
            // initialise proprement les autres compteurs si le doc n'existe pas
            booksDownloaded: 0,
            videosWatched: 0,
            iaGptVisionQuestions: 0,
            examsDownloaded: 0,
            examsCorrectionsDownloaded: 0,
            iaTextQuestions: 0,
            iaImageQuestions: 0,
          },
        },
        { new: true, upsert: true }
      );
    } catch (e) {
      // Conflit rare d'upsert → on retente sans upsert
      if (e && e.code === 11000) {
        usage = await MonthlyUsage.findOneAndUpdate(
          { user: req.user._id, period },
          { $inc: { supportRequestsCreated: 1 } },
          { new: true }
        );
      } else {
        throw e;
      }
    }

    // Si on dépasse le quota, on annule l'incrément et on refuse
    if ((usage?.supportRequestsCreated || 0) > REQUESTS_PER_MONTH) {
      await MonthlyUsage.updateOne(
        { _id: usage._id },
        { $inc: { supportRequestsCreated: -1 } }
      );
      return res
        .status(403)
        .json({ message: `Quota mensuel atteint : ${REQUESTS_PER_MONTH} requêtes maximum.` });
    }

    // ✅ Création de la nouvelle demande
    let supportRequest;
    try {
      supportRequest = await SupportRequest.create({
        student: req.user._id,
        topic,
        type,
        level,
        description: description || "",
        serie: serie || "",
      });
    } catch (err) {
      // rollback du quota si la création échoue
      await MonthlyUsage.updateOne(
        { user: req.user._id, period },
        { $inc: { supportRequestsCreated: -1 } }
      );
      throw err;
    }

    return res.status(201).json(supportRequest);
  } catch (error) {
    console.error("❌ Erreur création demande :", error);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};




// exports.createSupportRequest = async (req, res) => {
//   try {
//     const { topic, type, level, description, serie } = req.body;

//     // ✅ Validation minimale des champs requis
//     if (!topic || !type || !level) {
//       return res.status(400).json({ message: "Les champs obligatoires sont manquants." });
//     }

//     // 🔒 Vérification : l'élève a-t-il une demande en cours ?
//     const existingRequest = await SupportRequest.findOne({
//       student: req.user._id,
//       status: { $in: ["en_attente", "acceptee"] },
//     });

//     if (existingRequest) {
//       return res.status(400).json({
//         message: "Vous avez déjà une demande de soutien en cours. Veuillez la terminer avant d’en créer une nouvelle.",
//       });
//     }

//     // ✅ QUOTA mensuel : max 5 requêtes par élève
//     const period = currentPeriod();
//     const incIfUnderLimit = await MonthlyUsage.updateOne(
//       { user: req.user._id, period, supportRequestsCreated: { $lt: REQUESTS_PER_MONTH } },
//       { $inc: { supportRequestsCreated: 1 } },
//       { upsert: true }
//     );
//     if (incIfUnderLimit.modifiedCount === 0 && !incIfUnderLimit.upsertedId) {
//       return res
//         .status(403)
//         .json({ message: "Quota mensuel atteint : 5 requêtes maximum." });
//     }

//     // ✅ Création de la nouvelle demande
//     const supportRequest = await SupportRequest.create({
//       student: req.user._id,
//       topic,
//       type,
//       level,
//       description: description || "",
//       serie: serie || "",
//     });

//     res.status(201).json(supportRequest);
//   } catch (error) {
//     console.error("❌ Erreur création demande :", error);
//     res.status(500).json({ message: "Erreur serveur." });
//   }
// };




exports.getStudentSupportRequests = async (req, res) => {
  try {
    const requests = await SupportRequest.find({ student: req.user._id })
      .populate("teacher", "fullName subjects schoolName city")
      .sort({ createdAt: -1 });

    res.status(200).json(requests);
  } catch (error) {
    console.error("❌ Erreur récupération demandes élève :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// ✅ 3. Voir les demandes adressées à un enseignant

exports.getTeacherSupportRequests = async (req, res) => {
  try {
    const requests = await SupportRequest.find({
      $or: [
        { teacher: null },
        { teacher: req.user._id },
      ],
    })
      .populate("student", "fullName level schoolName city")
      .sort({ createdAt: -1 });

    res.status(200).json(requests);
  } catch (error) {
    console.error("❌ Erreur récupération demandes enseignant :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};




// ✅ 4. Mettre à jour le statut (acceptée, refusée, terminée…)

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

    // Si aucun enseignant encore assigné → assigner celui qui répond
    if (!request.teacher) {
      request.teacher = req.user._id;
    } else if (request.teacher.toString() !== req.user._id.toString()) {
      return res.status(403).json({ message: "Cette demande est déjà assignée à un autre enseignant." });
    }

    request.status = status;
    await request.save();

    res.status(200).json(request);
  } catch (error) {
    console.error("❌ Erreur mise à jour statut :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};
