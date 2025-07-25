const Book = require("../models/bookModel");
const { getOrCreateMonthlyUsage } = require("../utils/getOrCreateMonthlyUsage");
const Exam = require("../models/Exam");
const cloudinary = require('cloudinary').v2;
const MonthlyUsage = require("../models/MonthlyUsage");


const BOOKS_LIMIT_PER_MONTH = 5;

// 📥 Téléchargement avec quota (abonnement requis)
const downloadBookWithLimit = async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);
    if (!book) return res.status(404).json({ message: "📘 Livre introuvable." });

    if (!req.user.isSubscribed) {
      return res.status(403).json({ message: "⛔ Abonnement requis pour télécharger." });
    }

    const usage = await getOrCreateMonthlyUsage(req.user._id);

   if (usage.booksDownloaded >= BOOKS_LIMIT_PER_MONTH) {
  return res.status(429).json({ message: "📚 Limite mensuelle atteinte." });
}

    usage.booksDownloaded += 1;
    await usage.save();

    // ✅ Incrémenter le compteur de téléchargement
    book.downloadCount = (book.downloadCount || 0) + 1;
    await book.save();

    return res.json({ downloadUrl: book.fileUrl });
  } catch (err) {
    console.error("❌ Erreur téléchargement livre :", err.message);
    res.status(500).json({ message: "Erreur lors du téléchargement." });
  }
};


const viewBook = async (req, res) => {
  const book = await Book.findById(req.params.id);
  if (!book) {
    return res.status(400).json({ message: "Livre introuvable" });
  }

  // if (!book.fileUrl.endsWith(".pdf")) {
  //   return res.status(400).json({ message: "Fichier PDF invalide ou manquant" });
  // }

  if (!book.fileUrl || typeof book.fileUrl !== "string") {
  return res.status(400).json({ message: "Lien vers le fichier manquant." });
}


  // ✅ Incrémenter viewCount
  book.viewCount = (book.viewCount || 0) + 1;
  await book.save();

  return res.json({ viewUrl: book.fileUrl });
};




// ✅ Afficher tous les livres
const getAllBooks = async (req, res) => {
  try {
    const books = await Book.find().sort({ createdAt: -1 });
    res.json(books);
  } catch (err) {
    res.status(500).json({ message: "❌ Erreur lors de la récupération des livres." });
  }
};

// ✅ Afficher un seul livre par ID
const getBookById = async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);
    if (!book) return res.status(404).json({ message: "📘 Livre non trouvé." });

    res.json(book);
  } catch (err) {
    res.status(500).json({ message: "❌ Erreur lors de la récupération du livre." });
  }
};


const downloadExamWithLimit = async (req, res) => {
  try {
    const exam = await Exam.findById(req.params.id);
    if (!exam) return res.status(404).json({ message: "Sujet introuvable." });

    if (!req.user.isSubscribed) {
      return res.status(403).json({ message: "⛔ Accès réservé aux abonnés." });
    }

    const usage = await getOrCreateMonthlyUsage(req.user._id);
    if (usage.examsDownloaded >= 3) {
      return res.status(429).json({
        message: "📄 Limite mensuelle atteinte (3 examens).",
      });
    }

    usage.examsDownloaded += 1;
    await usage.save();

    exam.subjectDownloadCount = (exam.subjectDownloadCount || 0) + 1;
    await exam.save();

    return res.json({ subjectUrl: exam.subjectUrl });
  } catch (err) {
    console.error("Erreur téléchargement examen :", err.message);
    res.status(500).json({ message: "Erreur lors du téléchargement." });
  }
};





const downloadCorrectionWithLimit = async (req, res) => {
  try {
    const exam = await Exam.findById(req.params.id);
    if (!exam) {
      return res.status(404).json({ message: "❌ Correction introuvable." });
    }

    if (!req.user.isSubscribed) {
      return res.status(403).json({ message: "⛔ Accès réservé aux abonnés." });
    }

    const usage = await getOrCreateMonthlyUsage(req.user._id);
    const current = usage.examsCorrectionsDownloaded || 0;

    if (current >= 3) {
      return res.status(429).json({
        message: "📄 Limite mensuelle de corrections atteinte (3 fichiers).",
      });
    }

    usage.examsCorrectionsDownloaded = current + 1;
    await usage.save();

    exam.correctionDownloadCount = (exam.correctionDownloadCount || 0) + 1;
    await exam.save();

    return res.json({ correctionUrl: exam.correctionUrl });
  } catch (err) {
    console.error("Erreur téléchargement correction :", err.message);
    res.status(500).json({ message: "Erreur lors du téléchargement." });
  }
};






module.exports = {
  downloadBookWithLimit,
  viewBook,
  getAllBooks,
  getBookById,
  downloadExamWithLimit,
  downloadCorrectionWithLimit,


};
