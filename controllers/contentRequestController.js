// controllers/contentRequestController.js
const ContentRequest = require("../models/ContentRequest");
const User = require("../models/userModel");
const nodemailer = require("nodemailer");

// ✅ Configuration email (Gmail)
const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: process.env.EMAIL_USER || "fahimtamlk@gmail.com",
    pass: process.env.EMAIL_PASS, // ⚠️ Mot de passe d'application Gmail
  },
});

// ✅ Envoyer email à l'admin
const sendAdminEmail = async (request, studentInfo) => {
  const contentTypeLabels = {
    video: "Cours vidéo",
    livre: "Livre / Manuel",
    exercices: "Exercices corrigés",
    fiche: "Fiche de révision",
    autre: "Autre",
  };

  const subjectLabels = {
    maths: "Mathématiques",
    physique: "Physique",
    chimie: "Chimie",
    svt: "SVT",
  };

  const mailOptions = {
    from: process.env.EMAIL_USER || "fahimtamlk@gmail.com",
    to: "fahimtamlk@gmail.com",
    subject: `🎓 Nouvelle demande de contenu - ${contentTypeLabels[request.contentType]}`,
    html: `
      <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
        <div style="background: linear-gradient(135deg, #1565C0, #0d47a1); padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
          <h1 style="color: white; margin: 0;">📚 FAHIMTA</h1>
          <p style="color: #e3f2fd; margin: 5px 0 0 0;">Nouvelle demande de contenu</p>
        </div>
        
        <div style="background: white; padding: 25px; border-radius: 0 0 8px 8px;">
          <h2 style="color: #1565C0; border-bottom: 2px solid #e3f2fd; padding-bottom: 10px;">
            📝 Détails de la demande
          </h2>
          
          <table style="width: 100%; margin-top: 15px;">
            <tr>
              <td style="padding: 8px 0; color: #666; font-weight: bold; width: 150px;">🎓 Élève :</td>
              <td style="padding: 8px 0;">${studentInfo.fullName}</td>
            </tr>
            <tr>
              <td style="padding: 8px 0; color: #666; font-weight: bold;">📞 Téléphone :</td>
              <td style="padding: 8px 0;">${studentInfo.phone || "Non renseigné"}</td>
            </tr>
            <tr>
              <td style="padding: 8px 0; color: #666; font-weight: bold;">🏫 École :</td>
              <td style="padding: 8px 0;">${studentInfo.schoolName || "Non renseignée"}</td>
            </tr>
            <tr>
              <td style="padding: 8px 0; color: #666; font-weight: bold;">📍 Ville :</td>
              <td style="padding: 8px 0;">${studentInfo.city || "Non renseignée"}</td>
            </tr>
          </table>
          
          <div style="margin: 20px 0; padding: 15px; background: #e3f2fd; border-left: 4px solid #1565C0; border-radius: 4px;">
            <table style="width: 100%;">
              <tr>
                <td style="padding: 5px 0; color: #0d47a1; font-weight: bold;">📦 Type :</td>
                <td style="padding: 5px 0;">${contentTypeLabels[request.contentType]}</td>
              </tr>
              <tr>
                <td style="padding: 5px 0; color: #0d47a1; font-weight: bold;">📚 Matière :</td>
                <td style="padding: 5px 0;">${subjectLabels[request.subject]}</td>
              </tr>
              <tr>
                <td style="padding: 5px 0; color: #0d47a1; font-weight: bold;">🎯 Niveau :</td>
                <td style="padding: 5px 0;">${request.level}</td>
              </tr>
              ${request.chapter ? `
              <tr>
                <td style="padding: 5px 0; color: #0d47a1; font-weight: bold;">📖 Chapitre :</td>
                <td style="padding: 5px 0;">${request.chapter}</td>
              </tr>
              ` : ''}
            </table>
          </div>
          
          <div style="margin: 20px 0;">
            <h3 style="color: #1565C0; margin-bottom: 10px;">💬 Description :</h3>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 4px; white-space: pre-wrap; line-height: 1.6;">
              ${request.description}
            </div>
          </div>
          
          <div style="margin-top: 25px; padding: 15px; background: #fff3e0; border-radius: 4px; text-align: center;">
            <p style="margin: 0; color: #e65100; font-weight: bold;">
              ⚡ Priorité : ${request.priority}/5
            </p>
          </div>
          
          <div style="margin-top: 20px; text-align: center;">
            <p style="color: #666; font-size: 12px;">
              📅 Demande créée le ${new Date(request.createdAt).toLocaleString('fr-FR')}
            </p>
          </div>
        </div>
        
        <div style="text-align: center; margin-top: 15px; color: #999; font-size: 12px;">
          <p>Ce message a été envoyé automatiquement par le système Fahimta</p>
        </div>
      </div>
    `,
  };

  try {
    await transporter.sendMail(mailOptions);
    console.log("✅ Email envoyé à l'admin pour demande #", request._id);
    return true;
  } catch (error) {
    console.error("❌ Erreur envoi email:", error);
    return false;
  }
};

// ✅ Créer une nouvelle demande (élève)
exports.createContentRequest = async (req, res) => {
  try {
    const studentId = req.user._id;
    const { contentType, subject, level, chapter, description, priority } = req.body;

    // Validation
    if (!contentType || !subject || !level || !description) {
      return res.status(400).json({ message: "Champs requis manquants." });
    }

    // Créer la demande
    const newRequest = await ContentRequest.create({
      student: studentId,
      contentType,
      subject,
      level,
      chapter: chapter || "",
      description,
      priority: priority || 3,
    });

    await newRequest.populate("student", "fullName phone schoolName city");

    // ✅ Envoyer email à l'admin
    const emailSent = await sendAdminEmail(newRequest, newRequest.student);
    
    if (emailSent) {
      newRequest.emailSent = true;
      await newRequest.save();
    }

    res.status(201).json({
      message: "✅ Votre demande a été envoyée avec succès ! L'admin sera notifié par email.",
      request: newRequest,
    });
  } catch (error) {
    console.error("Erreur createContentRequest:", error);
    res.status(500).json({ message: "Erreur serveur lors de la création de la demande." });
  }
};

// ✅ Récupérer les demandes d'un élève
exports.getMyContentRequests = async (req, res) => {
  try {
    const studentId = req.user._id;
    const requests = await ContentRequest.find({ student: studentId })
      .sort({ createdAt: -1 })
      .select("-adminNotes"); // Ne pas exposer les notes admin à l'élève

    res.json(requests);
  } catch (error) {
    console.error("Erreur getMyContentRequests:", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// ✅ Récupérer toutes les demandes (admin)
exports.getAllContentRequests = async (req, res) => {
  try {
    const { status, page = 1, limit = 20 } = req.query;

    const filter = {};
    if (status) filter.status = status;

    const skip = (page - 1) * limit;

    const [requests, total] = await Promise.all([
      ContentRequest.find(filter)
        .populate("student", "fullName phone schoolName city")
        .sort({ createdAt: -1 })
        .skip(skip)
        .limit(parseInt(limit)),
      ContentRequest.countDocuments(filter),
    ]);

    res.json({
      requests,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total,
        pages: Math.ceil(total / limit),
      },
    });
  } catch (error) {
    console.error("Erreur getAllContentRequests:", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// ✅ Mettre à jour le statut d'une demande (admin)
exports.updateContentRequestStatus = async (req, res) => {
  try {
    const { id } = req.params;
    const { status, adminNotes } = req.body;

    const request = await ContentRequest.findById(id);
    if (!request) {
      return res.status(404).json({ message: "Demande introuvable." });
    }

    if (status) request.status = status;
    if (adminNotes !== undefined) request.adminNotes = adminNotes;

    if (status === "terminee" && !request.processedAt) {
      request.processedAt = new Date();
      request.processedBy = req.user._id;
    }

    await request.save();
    await request.populate("student", "fullName phone schoolName city");

    res.json({
      message: "✅ Demande mise à jour.",
      request,
    });
  } catch (error) {
    console.error("Erreur updateContentRequestStatus:", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

// ✅ Supprimer une demande (admin)
exports.deleteContentRequest = async (req, res) => {
  try {
    const { id } = req.params;
    const deleted = await ContentRequest.findByIdAndDelete(id);

    if (!deleted) {
      return res.status(404).json({ message: "Demande introuvable." });
    }

    res.json({ message: "✅ Demande supprimée." });
  } catch (error) {
    console.error("Erreur deleteContentRequest:", error);
    res.status(500).json({ message: "Erreur serveur." });
  }
};
