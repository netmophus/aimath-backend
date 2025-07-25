const SupportRequest = require("../models/SupportRequest");
const User = require("../models/userModel");

// ✅ 1. Créer une demande de soutien


exports.createSupportRequest = async (req, res) => {
  try {
    const { topic, type, level, description, serie } = req.body;

    // ✅ Validation minimale des champs requis
    if (!topic || !type || !level) {
      return res.status(400).json({ message: "Les champs obligatoires sont manquants." });
    }

    // 🔒 Vérification : l'élève a-t-il une demande en cours ?
    const existingRequest = await SupportRequest.findOne({
      student: req.user._id,
      status: { $in: ["en_attente", "acceptee"] },
    });

    if (existingRequest) {
      return res.status(400).json({
        message: "Vous avez déjà une demande de soutien en cours. Veuillez la terminer avant d’en créer une nouvelle.",
      });
    }

    // ✅ Création de la nouvelle demande
    const supportRequest = await SupportRequest.create({
      student: req.user._id,
      topic,
      type,
      level,
      description: description || "",
      serie: serie || "",
    });

    res.status(201).json(supportRequest);
  } catch (error) {
    console.error("❌ Erreur création demande :", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};



// ✅ 2. Voir les demandes d’un élève
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
