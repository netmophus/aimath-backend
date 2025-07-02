const express = require("express");
const router = express.Router();
const bookController = require("../controllers/bookController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const uploadBook = require("../middlewares/uploadBook"); // ✅ middleware combiné cover + pdf

// 🔐 Créer un livre (admin uniquement)
router.post(
  "/",
  authMiddleware,
  authorizeRoles("admin"),
  uploadBook, // ✅ c'est bien une fonction maintenant
  bookController.createBook
);

// 🔐 Modifier un livre (admin uniquement)
router.put(
  "/:id",
  authMiddleware,
  authorizeRoles("admin"),
  uploadBook, // ✅ même middleware pour update
  bookController.updateBook
);

// 🔐 Supprimer un livre (admin uniquement)
router.delete(
  "/:id",
  authMiddleware,
  authorizeRoles("admin"),
  bookController.deleteBook
);

// 🌍 Afficher tous les livres (public)
router.get("/", bookController.getAllBooks);

// 🌍 Afficher un seul livre par ID (optionnel)
router.get("/:id", bookController.getBookById);

module.exports = router;
