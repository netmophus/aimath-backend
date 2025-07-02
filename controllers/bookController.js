// const Book = require("../models/bookModel");
// const cloudinary = require("../config/cloudinary");

// const createBook = async (req, res) => {
//   try {
//     const { title, author, description, level, badge } = req.body;

//     if (!req.files || !req.files.cover || !req.files.pdf) {
//       return res.status(400).json({ message: "Image de couverture et PDF requis." });
//     }

//     // 📤 Upload image de couverture
//     const coverUpload = await cloudinary.uploader.upload_stream_async(req.files.cover[0], "fahimta_books/covers");

//     // 📤 Upload du PDF
//     const pdfUpload = await cloudinary.uploader.upload_stream_async(req.files.pdf[0], "fahimta_books/pdfs", "raw");

//     const newBook = new Book({
//       title,
//       author,
//       description,
//       level,
//       badge,
//       coverImage: coverUpload.secure_url,
//       fileUrl: pdfUpload.secure_url,
//     });

//     await newBook.save();
//     res.status(201).json({ message: "Livre ajouté avec succès", book: newBook });
//   } catch (err) {
//     console.error("Erreur création livre :", err);
//     res.status(500).json({ message: "Erreur lors de l'ajout du livre." });
//   }
// };

// module.exports = {
//   createBook,
//   // Tu peux aussi ajouter updateBook, deleteBook, getAllBooks ici
// };





const Book = require("../models/bookModel");


const createBook = async (req, res) => {
  try {
    console.log("📥 Body :", req.body);
    console.log("📁 Fichiers :", req.files);

    const { title, author, description, level, badge } = req.body;

    const coverImage = req.files?.cover?.[0]?.path;
    const fileUrl = req.files?.pdf?.[0]?.path;

    if (!coverImage || !fileUrl) {
      return res.status(400).json({ message: "📂 Couverture et PDF requis." });
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

    console.log("✅ Livre enregistré avec succès :", book._id);
    res.status(201).json(book);
  } catch (err) {
    console.error("❌ Erreur :", err.message);
    res.status(500).json({ message: "❌ Erreur lors de la création du livre." });
  }
};


// ✅ Modifier un livre
const updateBook = async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);
    if (!book) return res.status(404).json({ message: "📘 Livre non trouvé." });

    const { title, author, description, level, badge } = req.body;

    // upload cover si fournie
    if (req.files?.cover?.[0]?.path) {
      const newCover = await uploadToCloudinary(req.files.cover[0].path, "books/covers", "image");
      book.coverImage = newCover;
    }

    // upload pdf si fourni
    if (req.files?.pdf?.[0]?.path) {
      const newPdf = await uploadToCloudinary(req.files.pdf[0].path, "books/pdfs", "raw");
      book.fileUrl = newPdf;
    }

    book.title = title || book.title;
    book.author = author || book.author;
    book.description = description || book.description;
    book.level = level || book.level;
    book.badge = badge || book.badge;

    await book.save();

    res.json(book);
  } catch (err) {
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
};
