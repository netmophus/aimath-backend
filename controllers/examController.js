const Exam = require("../models/Exam");
const Notification = require('../models/Notification'); // adapte le chemin si besoin





exports.createExam = async (req, res) => {
  try {
    const { title, level, description, badge } = req.body;

    // ✅ Vérification des champs obligatoires
    if (!title || !level || !description || !badge) {
      return res.status(400).json({ message: "Tous les champs sont requis." });
    }

    // ✅ Accès aux URLs Cloudinary
    const subjectUrl = req.files?.subject?.[0]?.path;
    const correctionUrl = req.files?.correction?.[0]?.path || null;
    const coverImage = req.files?.cover?.[0]?.path || null;

    if (!subjectUrl) {
      return res.status(400).json({ message: "Le fichier du sujet est obligatoire." });
    }

    // ✅ Création de l'examen
    const newExam = new Exam({
      title,
      level,
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
      linkTo: 'ExamList', // Ce nom doit correspondre au nom de l'écran dans ton navigateur
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
    const { title, level, description, badge } = req.body;

    const updateData = { title, level, description, badge };

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
