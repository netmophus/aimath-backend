// const express = require("express");
// const router = express.Router();
// const { createChapter, getChaptersByClasseAndSubject , deleteChapterById, updateChapterById, } = require("../controllers/chapterController");
// const authMiddleware = require("../middlewares/authMiddleware");
// const { authorizeRoles } = require("../middlewares/roleMiddleware");
// // const uploadChapitre = require("../middlewares/uploadChapitreMiddleware");

// // Seul l'admin peut ajouter un chapitre
// router.post(
//   "/",
//   authMiddleware,
//   authorizeRoles("admin"),
//   uploadChapitre.fields([
//     { name: "imageFile", maxCount: 1 },
//     { name: "pdfs", maxCount: 10 },
//   ]),
//   createChapter
// );


// router.delete(
//   "/:id",
//   authMiddleware,
//   authorizeRoles("admin"),
//   deleteChapterById
// );



// router.put(
//   "/:id",
//   authMiddleware,
//   authorizeRoles("admin"),
//   uploadChapitre.fields([
//     { name: "imageFile", maxCount: 1 },
//     { name: "pdfs", maxCount: 10 },
//   ]),
//   updateChapterById
// );


// // Tous les utilisateurs peuvent consulter les chapitres de mathématiques
// router.get("/:level/:classe", getChaptersByClasseAndSubject);



// module.exports = router;
