const express = require("express");
const router = express.Router();
const LibraryBook = require("../models/LibraryBookModel");
const LibrarySubject = require("../models/LibrarySubjectModel");
const auth = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const multer = require("multer");
const path = require("path");
const fs = require("fs");

// Configuration de multer pour l'upload des fichiers
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    const uploadPath = "uploads/books";
    if (!fs.existsSync(uploadPath)) {
      fs.mkdirSync(uploadPath, { recursive: true });
    }
    cb(null, uploadPath);
  },
  filename: function (req, file, cb) {
    // Générer un nom de fichier unique
    const uniqueSuffix = Date.now() + "-" + Math.round(Math.random() * 1e9);
    cb(null, `book-${uniqueSuffix}${path.extname(file.originalname)}`);
  },
});

const upload = multer({
  storage: storage,
  limits: {
    fileSize: 50 * 1024 * 1024, // 50MB max
  },
  fileFilter: function (req, file, cb) {
    // Accepter seulement les fichiers PDF
    if (file.mimetype === "application/pdf") {
      cb(null, true);
    } else {
      cb(new Error("Seuls les fichiers PDF sont autorisés"), false);
    }
  },
});

// ✅ Créer un nouveau livre
router.post("/books", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const {
      title,
      author,
      description,
      subject,
      level,
      pages,
      year,
      coverImageUrl,
      summaryUrl,
      tags,
      language = "fr",
    } = req.body;

    // Validation des données
    if (!title || !author || !description || !subject || !level || !pages || !year || !coverImageUrl || !summaryUrl) {
      return res.status(400).json({
        success: false,
        message: "Tous les champs obligatoires doivent être remplis",
      });
    }

    // Sommaire par défaut
    const parsedSummary = ["Chapitre 1: Introduction", "Chapitre 2: Développement", "Chapitre 3: Conclusion"];

    // Parser les tags si fournis
    let parsedTags = [];
    if (tags) {
      try {
        parsedTags = typeof tags === "string" ? JSON.parse(tags) : tags;
      } catch (error) {
        console.warn("Erreur parsing tags:", error);
      }
    }

    const book = new LibraryBook({
      title,
      author,
      description,
      subject,
      level,
      pages: parseInt(pages),
      year: parseInt(year),
      summary: parsedSummary,
      tags: parsedTags,
      language,
      coverImageUrl,
      summaryUrl,
      addedBy: req.user.id,
    });

    await book.save();

    res.status(201).json({
      success: true,
      message: "Livre créé avec succès",
      book: {
        id: book._id,
        title: book.title,
        author: book.author,
        subject: book.subject,
        level: book.level,
        isAvailable: book.isAvailable,
      },
    });
  } catch (error) {
    console.error("Erreur création livre:", error);
    
    // Supprimer le fichier uploadé en cas d'erreur
    if (req.file) {
      try {
        fs.unlinkSync(`uploads/books/${req.file.filename}`);
      } catch (unlinkError) {
        console.error("Erreur suppression fichier:", unlinkError);
      }
    }

    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la création du livre",
      error: error.message,
    });
  }
});

// ✅ Obtenir tous les livres (avec pagination et filtres)
router.get("/books", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const {
      page = 1,
      limit = 20,
      search,
      subject,
      level,
      isAvailable,
      sortBy = "createdAt",
      sortOrder = "desc",
    } = req.query;

    // Construire le filtre
    const filter = {};
    
    if (search) {
      filter.$or = [
        { title: { $regex: search, $options: "i" } },
        { author: { $regex: search, $options: "i" } },
        { description: { $regex: search, $options: "i" } },
      ];
    }

    if (subject) filter.subject = subject;
    if (level) filter.level = level;
    if (isAvailable !== undefined) filter.isAvailable = isAvailable === "true";

    // Pagination
    const skip = (parseInt(page) - 1) * parseInt(limit);
    const sort = { [sortBy]: sortOrder === "desc" ? -1 : 1 };

    const books = await LibraryBook.find(filter)
      .populate("addedBy", "name email")
      .populate("subject", "name color")
      .sort(sort)
      .skip(skip)
      .limit(parseInt(limit));

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
router.get("/books/:id", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const book = await LibraryBook.findById(req.params.id)
      .populate("addedBy", "name email")
      .populate("subject", "name color");

    if (!book) {
      return res.status(404).json({
        success: false,
        message: "Livre non trouvé",
      });
    }

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

// ✅ Modifier un livre
router.put("/books/:id", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const book = await LibraryBook.findById(req.params.id);

    if (!book) {
      return res.status(404).json({
        success: false,
        message: "Livre non trouvé",
      });
    }

    const {
      title,
      author,
      description,
      subject,
      level,
      pages,
      year,
      coverImageUrl,
      summaryUrl,
      tags,
      language,
      isAvailable,
    } = req.body;

    // Mettre à jour les champs
    if (title) book.title = title;
    if (author) book.author = author;
    if (description) book.description = description;
    if (subject) book.subject = subject;
    if (level) book.level = level;
    if (pages) book.pages = parseInt(pages);
    if (year) book.year = parseInt(year);
    if (language) book.language = language;
    if (isAvailable !== undefined) book.isAvailable = isAvailable === "true";

    if (coverImageUrl) book.coverImageUrl = coverImageUrl;
    if (summaryUrl) book.summaryUrl = summaryUrl;

    if (tags) {
      try {
        book.tags = typeof tags === "string" ? JSON.parse(tags) : tags;
      } catch (error) {
        console.warn("Erreur parsing tags:", error);
      }
    }

    // Mise à jour des URLs
    if (coverImageUrl) book.coverImageUrl = coverImageUrl;
    if (summaryUrl) book.summaryUrl = summaryUrl;

    await book.save();

    res.json({
      success: true,
      message: "Livre modifié avec succès",
      book,
    });
  } catch (error) {
    console.error("Erreur modification livre:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la modification du livre",
    });
  }
});

// ✅ Supprimer un livre
router.delete("/books/:id", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const book = await LibraryBook.findById(req.params.id);

    if (!book) {
      return res.status(404).json({
        success: false,
        message: "Livre non trouvé",
      });
    }

    // Plus besoin de supprimer de fichier physique (utilisation d'URLs)

    await LibraryBook.findByIdAndDelete(req.params.id);

    res.json({
      success: true,
      message: "Livre supprimé avec succès",
    });
  } catch (error) {
    console.error("Erreur suppression livre:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la suppression du livre",
    });
  }
});

// ✅ Basculer la disponibilité d'un livre
router.patch("/books/:id/toggle-availability", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const book = await LibraryBook.findById(req.params.id);

    if (!book) {
      return res.status(404).json({
        success: false,
        message: "Livre non trouvé",
      });
    }

    book.isAvailable = !book.isAvailable;
    await book.save();

    res.json({
      success: true,
      message: `Livre ${book.isAvailable ? "activé" : "désactivé"} avec succès`,
      book: {
        id: book._id,
        title: book.title,
        isAvailable: book.isAvailable,
      },
    });
  } catch (error) {
    console.error("Erreur basculement disponibilité:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la modification de la disponibilité",
    });
  }
});

// ✅ Obtenir les statistiques de la bibliothèque
router.get("/stats", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const totalBooks = await LibraryBook.countDocuments();
    const availableBooks = await LibraryBook.countDocuments({ isAvailable: true });
    const totalDownloads = await LibraryBook.aggregate([
      { $group: { _id: null, total: { $sum: "$downloads" } } }
    ]);
    const totalViews = await LibraryBook.aggregate([
      { $group: { _id: null, total: { $sum: "$views" } } }
    ]);

    const booksBySubject = await LibraryBook.aggregate([
      { $group: { _id: "$subject", count: { $sum: 1 } } }
    ]);

    const booksByLevel = await LibraryBook.aggregate([
      { $group: { _id: "$level", count: { $sum: 1 } } }
    ]);

    res.json({
      success: true,
      stats: {
        totalBooks,
        availableBooks,
        totalDownloads: totalDownloads[0]?.total || 0,
        totalViews: totalViews[0]?.total || 0,
        booksBySubject,
        booksByLevel,
      },
    });
  } catch (error) {
    console.error("Erreur récupération statistiques:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la récupération des statistiques",
    });
  }
});

// ===== ROUTES POUR LES MATIÈRES =====

// ✅ Récupérer toutes les matières (admin)
router.get("/subjects", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const subjects = await LibrarySubject.find()
      .populate("addedBy", "name email")
      .sort({ createdAt: -1 });

    res.json({
      success: true,
      data: subjects,
    });
  } catch (error) {
    console.error("Erreur récupération matières:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la récupération des matières",
    });
  }
});

// ✅ Créer une nouvelle matière (admin)
router.post("/subjects", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const { name, description, icon, color } = req.body;

    // Vérifier si la matière existe déjà
    const existingSubject = await LibrarySubject.findOne({ name });
    if (existingSubject) {
      return res.status(400).json({
        success: false,
        message: "Une matière avec ce nom existe déjà",
      });
    }

    const subject = new LibrarySubject({
      name,
      description,
      icon: icon || "SchoolIcon",
      color: color || "#3b82f6",
      addedBy: req.user.id,
    });

    await subject.save();

    res.status(201).json({
      success: true,
      message: "Matière créée avec succès",
      data: subject,
    });
  } catch (error) {
    console.error("Erreur création matière:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la création de la matière",
    });
  }
});

// ✅ Modifier une matière (admin)
router.put("/subjects/:id", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const { name, description, icon, color } = req.body;
    const subjectId = req.params.id;

    // Vérifier si la matière existe
    const subject = await LibrarySubject.findById(subjectId);
    if (!subject) {
      return res.status(404).json({
        success: false,
        message: "Matière non trouvée",
      });
    }

    // Vérifier si le nouveau nom existe déjà (si différent)
    if (name !== subject.name) {
      const existingSubject = await LibrarySubject.findOne({ name });
      if (existingSubject) {
        return res.status(400).json({
          success: false,
          message: "Une matière avec ce nom existe déjà",
        });
      }
    }

    // Mettre à jour la matière
    const updatedSubject = await LibrarySubject.findByIdAndUpdate(
      subjectId,
      {
        name,
        description,
        icon: icon || subject.icon,
        color: color || subject.color,
        lastModified: new Date(),
      },
      { new: true }
    );

    res.json({
      success: true,
      message: "Matière modifiée avec succès",
      data: updatedSubject,
    });
  } catch (error) {
    console.error("Erreur modification matière:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la modification de la matière",
    });
  }
});

// ✅ Supprimer une matière (admin)
router.delete("/subjects/:id", auth, authorizeRoles("admin"), async (req, res) => {
  try {
    const subjectId = req.params.id;

    // Vérifier si la matière existe
    const subject = await LibrarySubject.findById(subjectId);
    if (!subject) {
      return res.status(404).json({
        success: false,
        message: "Matière non trouvée",
      });
    }

    // Vérifier s'il y a des livres associés à cette matière
    const booksCount = await LibraryBook.countDocuments({ subject: subjectId });
    if (booksCount > 0) {
      return res.status(400).json({
        success: false,
        message: `Impossible de supprimer cette matière car ${booksCount} livre(s) y sont associés`,
      });
    }

    await LibrarySubject.findByIdAndDelete(subjectId);

    res.json({
      success: true,
      message: "Matière supprimée avec succès",
    });
  } catch (error) {
    console.error("Erreur suppression matière:", error);
    res.status(500).json({
      success: false,
      message: "Erreur serveur lors de la suppression de la matière",
    });
  }
});

module.exports = router;
