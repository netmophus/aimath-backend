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
  uploadBook,
  bookController.createBook
);


// 🔓 Obtenir la liste des livres (accès public ou authentifié selon besoin)
router.get("/", bookController.getAllBooks);


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

module.exports = router;



