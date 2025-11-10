const express = require("express");
const router = express.Router();
const LibraryBook = require("../models/LibraryBookModel"); // Modèle pour la bibliothèque
const LibrarySubject = require("../models/LibrarySubjectModel"); // Modèle pour les matières
const auth = require("../middlewares/authMiddleware");

// ✅ Obtenir tous les sujets/matières disponibles
router.get("/subjects", auth, async (req, res) => {
  try {
    console.log("🔄 Récupération des matières depuis la base de données...");
    
    // Récupérer toutes les matières depuis la base de données
    const subjects = await LibrarySubject.find()
      .populate("addedBy", "name email")
      .sort({ createdAt: -1 });

    console.log(`📚 ${subjects.length} matières trouvées:`, subjects.map(s => s.name));

    // Calculer le nombre de livres pour chaque matière
    const subjectsWithBookCount = await Promise.all(
      subjects.map(async (subject) => {
        const bookCount = await LibraryBook.countDocuments({
          subject: subject._id,
          isAvailable: true,
        });
        console.log(`📖 ${subject.name}: ${bookCount} livres`);
        return {
          ...subject.toObject(),
          bookCount,
        };
      })
    );

    console.log("✅ Envoi des matières au frontend:", subjectsWithBookCount.length);

    res.json({
      success: true,
      data: subjectsWithBookCount,
    });
  } catch (error) {
    console.error("❌ Erreur récupération sujets:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la récupération des sujets",
    });
  }
});

// ✅ Obtenir les livres d'une matière spécifique
router.get("/subjects/:subjectId/books", auth, async (req, res) => {
  try {
    const { subjectId } = req.params;
    console.log("🔄 Recherche des livres pour la matière:", subjectId);
    
    const { search, level, page = 1, limit = 12 } = req.query;

    // Construire le filtre
    const filter = { subject: subjectId, isAvailable: true };
    console.log("🔍 Filtre appliqué:", filter);
    
    if (search) {
      filter.$or = [
        { title: { $regex: search, $options: "i" } },
        { author: { $regex: search, $options: "i" } },
        { description: { $regex: search, $options: "i" } },
      ];
    }

    if (level && level !== "all") {
      filter.level = level;
    }

    // Pagination
    const skip = (parseInt(page) - 1) * parseInt(limit);

    const books = await LibraryBook.find(filter)
      .populate("subject", "name color")
      .populate("addedBy", "name email")
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(parseInt(limit));
    
    console.log(`📚 ${books.length} livres trouvés pour la matière ${subjectId}`);

    const totalBooks = await LibraryBook.countDocuments(filter);

    res.json({
      success: true,
      data: books,
      pagination: {
        currentPage: parseInt(page),
        totalPages: Math.ceil(totalBooks / parseInt(limit)),
        totalBooks,
        hasNext: skip + books.length < totalBooks,
        hasPrev: parseInt(page) > 1,
      },
    });
  } catch (error) {
    console.error("Erreur récupération livres:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la récupération des livres",
    });
  }
});

// ✅ Obtenir un livre spécifique
router.get("/books/:bookId", auth, async (req, res) => {
  try {
    const { bookId } = req.params;

    const book = await LibraryBook.findById(bookId).select(
      "title author description summary pages year level downloads views isAvailable filePath"
    );

    if (!book) {
      return res.status(404).json({
        success: false,
        message: "Livre non trouvé",
      });
    }

    // Incrémenter le nombre de vues
    await LibraryBook.findByIdAndUpdate(bookId, { $inc: { views: 1 } });

    res.json({
      success: true,
      book,
    });
  } catch (error) {
    console.error("Erreur récupération livre:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la récupération du livre",
    });
  }
});

// ✅ Télécharger un livre
router.get("/books/:bookId/download", auth, async (req, res) => {
  try {
    const { bookId } = req.params;
    const userId = req.user.id;

    const book = await LibraryBook.findById(bookId);

    if (!book) {
      return res.status(404).json({
        success: false,
        message: "Livre non trouvé",
      });
    }

    if (!book.isAvailable) {
      return res.status(403).json({
        success: false,
        message: "Ce livre n'est pas encore disponible",
      });
    }

    // Vérifier si l'utilisateur a accès (abonnement premium)
    if (!req.user.isSubscribed) {
      return res.status(403).json({
        success: false,
        message: "Accès premium requis pour télécharger ce livre",
      });
    }

    // Incrémenter le nombre de téléchargements
    await LibraryBook.findByIdAndUpdate(bookId, { $inc: { downloads: 1 } });

    // Log du téléchargement (optionnel)
    console.log(`Livre ${bookId} téléchargé par utilisateur ${userId}`);

    // Retourner le chemin du fichier ou rediriger vers le fichier
    res.json({
      success: true,
      message: "Téléchargement autorisé",
      downloadUrl: `/uploads/books/${book.filePath}`,
    });
  } catch (error) {
    console.error("Erreur téléchargement livre:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors du téléchargement",
    });
  }
});

// ✅ Rechercher des livres dans toutes les matières
router.get("/search", auth, async (req, res) => {
  try {
    const { q, page = 1, limit = 12 } = req.query;

    if (!q || q.trim().length < 2) {
      return res.status(400).json({
        success: false,
        message: "Terme de recherche requis (minimum 2 caractères)",
      });
    }

    const filter = {
      $or: [
        { title: { $regex: q, $options: "i" } },
        { author: { $regex: q, $options: "i" } },
        { description: { $regex: q, $options: "i" } },
        { summary: { $regex: q, $options: "i" } },
      ],
    };

    const skip = (parseInt(page) - 1) * parseInt(limit);

    const books = await LibraryBook.find(filter)
      .select("title author description subject pages year level downloads views isAvailable")
      .sort({ downloads: -1, views: -1 })
      .skip(skip)
      .limit(parseInt(limit));

    const totalBooks = await LibraryBook.countDocuments(filter);

    res.json({
      success: true,
      books,
      query: q,
      pagination: {
        currentPage: parseInt(page),
        totalPages: Math.ceil(totalBooks / parseInt(limit)),
        totalBooks,
        hasNext: skip + books.length < totalBooks,
        hasPrev: parseInt(page) > 1,
      },
    });
  } catch (error) {
    console.error("Erreur recherche livres:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la recherche",
    });
  }
});

// ✅ Obtenir les livres les plus populaires
router.get("/popular", auth, async (req, res) => {
  try {
    const { limit = 10 } = req.query;

    const books = await LibraryBook.find({ isAvailable: true })
      .select("title author description subject pages year downloads views")
      .sort({ downloads: -1, views: -1 })
      .limit(parseInt(limit));

    res.json({
      success: true,
      books,
    });
  } catch (error) {
    console.error("Erreur récupération livres populaires:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la récupération des livres populaires",
    });
  }
});

module.exports = router;
