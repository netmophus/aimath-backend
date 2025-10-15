const Exam = require("../models/Exam");
const Notification = require('../models/Notification'); // adapte le chemin si besoin





exports.createExam = async (req, res) => {
  try {
    const { title, level, subject, description, badge, coverSupabaseUrl, subjectSupabaseUrl, correctionSupabaseUrl } = req.body;

    // ✅ Vérification des champs obligatoires
    if (!title || !level || !description || !badge) {
      return res.status(400).json({ message: "Tous les champs sont requis." });
    }

    // ✅ Gestion de l'image : soit upload Cloudinary, soit lien Supabase
    let coverImage;
    if (req.files?.cover?.[0]?.path) {
      coverImage = req.files.cover[0].path; // Upload Cloudinary
    } else if (coverSupabaseUrl) {
      coverImage = coverSupabaseUrl; // Lien Supabase
    }

    // ✅ Gestion du sujet : soit upload Cloudinary, soit lien Supabase
    let subjectUrl;
    if (req.files?.subject?.[0]?.path) {
      subjectUrl = req.files.subject[0].path; // Upload Cloudinary
    } else if (subjectSupabaseUrl) {
      subjectUrl = subjectSupabaseUrl; // Lien Supabase
    }

    // ✅ Gestion de la correction : soit upload Cloudinary, soit lien Supabase
    let correctionUrl;
    if (req.files?.correction?.[0]?.path) {
      correctionUrl = req.files.correction[0].path; // Upload Cloudinary
    } else if (correctionSupabaseUrl) {
      correctionUrl = correctionSupabaseUrl; // Lien Supabase
    }

    if (!subjectUrl) {
      return res.status(400).json({ message: "Le fichier du sujet est obligatoire." });
    }

    // ✅ Création de l'examen
    const newExam = new Exam({
      title,
      level,
      subject: subject || "maths",
      description,
      badge,
      subjectUrl,
      correctionUrl,
      coverImage,
    });

    await newExam.save();

    // ✅ Création de la notification
    await Notification.create({
      title: `📝 Nouvel examen ajouté : ${title}`,
      type: 'content',
      linkTo: 'ExamList',
    });

    res.status(201).json({
      message: "✅ Sujet d'examen ajouté avec succès.",
      exam: newExam,
    });
  } catch (error) {
    console.error("Erreur création exam :", error.message);
    res.status(500).json({ message: "❌ Erreur serveur lors de l'ajout de l'examen." });
  }
};




exports.getAllExams = async (req, res) => {
  try {
    const exams = await Exam.find().sort({ createdAt: -1 });
    res.json(exams);
  } catch (error) {
    res.status(500).json({ message: "Erreur lors du chargement des sujets." });
  }
};

exports.updateExam = async (req, res) => {
  try {
    const { title, level, subject, description, badge } = req.body;

    const updateData = { title, level, subject, description, badge };

    if (req.files?.pdf?.[0]?.path) updateData.fileUrl = req.files.pdf[0].path;
    if (req.files?.cover?.[0]?.path) updateData.coverImage = req.files.cover[0].path;

    const exam = await Exam.findByIdAndUpdate(req.params.id, updateData, { new: true });

    if (!exam) return res.status(404).json({ message: "Sujet non trouvé." });

    res.json({ message: "Sujet mis à jour avec succès." });
  } catch (error) {
    res.status(500).json({ message: "Erreur lors de la mise à jour." });
  }
};

exports.deleteExam = async (req, res) => {
  try {
    const exam = await Exam.findByIdAndDelete(req.params.id);
    if (!exam) return res.status(404).json({ message: "Sujet non trouvé." });

    res.json({ message: "Sujet supprimé." });
  } catch (error) {
    res.status(500).json({ message: "Erreur lors de la suppression." });
  }
};
