
const { getOrCreateMonthlyUsage } = require("../utils/getOrCreateMonthlyUsage");
const Book = require("../models/bookModel");
const Notification = require('../models/Notification'); // modèle Mongoose


// const createBook = async (req, res) => {
//   try {
//     console.log("📥 Body :", req.body);
//     console.log("📁 Fichiers :", req.files);

//     const { title, author, description, level, badge } = req.body;

//     const coverImage = req.files?.cover?.[0]?.path;
//     const fileUrl = req.files?.pdf?.[0]?.path;

//     if (!coverImage || !fileUrl) {
//       return res.status(400).json({ message: "📂 Couverture et PDF requis." });
//     }

//     const book = await Book.create({
//       title,
//       author,
//       description,
//       level,
//       badge,
//       coverImage,
//       fileUrl,
//     });

//     console.log("✅ Livre enregistré avec succès :", book._id);
//     res.status(201).json(book);
//   } catch (err) {
//     console.error("❌ Erreur :", err.message);
//     res.status(500).json({ message: "❌ Erreur lors de la création du livre." });
//   }
// };


// ✅ Modifier un livre


const createBook = async (req, res) => {
  try {
    const { title, author, description, level, badge, imageSupabaseUrl, bookSupabaseUrl } = req.body;

    // ✅ Gestion de l'image : soit upload Cloudinary, soit lien Supabase
    let coverImage;
    if (req.files?.cover?.[0]?.path) {
      coverImage = req.files.cover[0].path; // Upload Cloudinary
    } else if (imageSupabaseUrl) {
      coverImage = imageSupabaseUrl; // Lien Supabase
    }

    // ✅ Gestion du fichier : soit upload Cloudinary, soit lien Supabase
    let fileUrl;
    if (req.files?.pdf?.[0]?.path) {
      fileUrl = req.files.pdf[0].path; // Upload Cloudinary
    } else if (bookSupabaseUrl) {
      fileUrl = bookSupabaseUrl; // Lien Supabase
    }

    // 🧾 Vérification
    if (!coverImage || !fileUrl) {
      return res.status(400).json({ message: "La couverture et le fichier PDF sont requis." });
    }

    const book = await Book.create({
      title,
      author,
      description,
      level,
      badge,
      coverImage,
      fileUrl,
    });

    await Notification.create({
      userId: null, // notification globale
      title: `📘 Nouveau livre ajouté : ${book.title}`,
      type: 'content',
      linkTo: 'BookList',
      isReadBy: [],
    });

    res.status(201).json(book);
  } catch (err) {
    console.error("Erreur création livre :", err.message);
    res.status(500).json({ message: "Erreur lors de la création du livre." });
  }
};





const updateBook = async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);
    if (!book) return res.status(404).json({ message: "📘 Livre non trouvé." });

    const { title, author, description, level, badge, imageSupabaseUrl, bookSupabaseUrl } = req.body;

    // ✅ Mise à jour de l'image : soit upload Cloudinary, soit lien Supabase
    if (req.files?.cover?.[0]?.path) {
      book.coverImage = req.files.cover[0].path; // Upload Cloudinary
    } else if (imageSupabaseUrl) {
      book.coverImage = imageSupabaseUrl; // Lien Supabase
    }

    // ✅ Mise à jour du fichier : soit upload Cloudinary, soit lien Supabase
    if (req.files?.pdf?.[0]?.path) {
      book.fileUrl = req.files.pdf[0].path; // Upload Cloudinary
    } else if (bookSupabaseUrl) {
      book.fileUrl = bookSupabaseUrl; // Lien Supabase
    }

    book.title = title || book.title;
    book.author = author || book.author;
    book.description = description || book.description;
    book.level = level || book.level;
    book.badge = badge || book.badge;

    await book.save();

    res.json(book);
  } catch (err) {
    console.error("Erreur mise à jour livre :", err.message);
    res.status(500).json({ message: "❌ Erreur lors de la mise à jour." });
  }
};

// ✅ Supprimer un livre
const deleteBook = async (req, res) => {
  try {
    const book = await Book.findByIdAndDelete(req.params.id);
    if (!book) return res.status(404).json({ message: "📘 Livre non trouvé." });

    res.json({ message: "🗑️ Livre supprimé avec succès." });
  } catch (err) {
    res.status(500).json({ message: "❌ Erreur lors de la suppression." });
  }
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





module.exports = {
  createBook,
  updateBook,
  deleteBook,
  getAllBooks,
  getBookById,
  //  downloadBookWithLimit,
  //  viewBook,
   
};
