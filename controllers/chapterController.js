
// const Chapter = require("../models/chapterModel");
// const path = require("path");


// const createChapter = async (req, res) => {
//   try {
//     const {
//   chapterNumber,
//   title,
//   description,
//   level,
//   classe,
//   serie, // ✅ Ajout
//   aiEnabled,
// } = req.body;


//     const pdfsMetadata = JSON.parse(req.body.pdfsMetadata || "[]");
//     const videosMetadata = JSON.parse(req.body.videos || "[]");

//     // 📄 Gérer les fichiers PDF
//     const uploadedPdfs = (req.files["pdfs"] || []).map((file, i) => ({
//       ...pdfsMetadata[i],
//       url: `/uploads/chapters/${file.filename}`,
//     }));

//     // 🎥 Les vidéos sont des liens, pas d’image à gérer
//     const uploadedVideos = videosMetadata;

//     // 📸 Image principale facultative
//     let mainImage = null;
//     if (req.files["imageFile"] && req.files["imageFile"][0]) {
//       mainImage = `/uploads/chapters/${req.files["imageFile"][0].filename}`;
//     }

//    const chapter = await Chapter.create({
//   chapterNumber,
//   title,
//   description,
//   level,
//   classe,
//   serie, // ✅ Ajout ici aussi
//   aiEnabled: aiEnabled === "true",
//   videos: uploadedVideos,
//   pdfs: uploadedPdfs,
//   image: mainImage,
// });


//     res.status(201).json({ message: "✅ Chapitre créé", chapter });
//   } catch (err) {
//     console.error("Erreur createChapter :", err);
//     res.status(500).json({ message: "Erreur serveur" });
//   }
// };




// const getChaptersByClasseAndSubject = async (req, res) => {
//   const { level, classe } = req.params;
//   const { serie } = req.query; // ✅ récupération de la série via la query string
//   const page = parseInt(req.query.page) || 1;
//   const limit = parseInt(req.query.limit) || 5;

//   try {
//     // ✅ Construction dynamique du filtre
//     const filter = { level, classe };
//     if (serie) {
//       filter.serie = serie;
//     }

//     const chapters = await Chapter.find(filter)
//       .skip((page - 1) * limit)
//       .limit(limit)
//       .sort({ chapterNumber: 1 });

//     const total = await Chapter.countDocuments(filter);

//     res.json({
//       chapters,
//       totalPages: Math.ceil(total / limit),
//       currentPage: page,
//     });
//   } catch (error) {
//     console.error("Erreur getChaptersByClasseAndSubject :", error);
//     res.status(500).json({ message: "Erreur lors de la récupération des chapitres." });
//   }
// };



// const deleteChapterById = async (req, res) => {
//   try {
//     const { id } = req.params;
//     const chapter = await Chapter.findByIdAndDelete(id);

//     if (!chapter) {
//       return res.status(404).json({ message: "Chapitre introuvable" });
//     }

//     res.json({ message: "✅ Chapitre supprimé avec succès" });
//   } catch (error) {
//     console.error("Erreur lors de la suppression :", error);
//     res.status(500).json({ message: "❌ Erreur serveur lors de la suppression" });
//   }
// };



// const updateChapterById = async (req, res) => {
//   try {
//     const { id } = req.params;

//     const {
//       chapterNumber,
//       title,
//       description,
//       level,
//       classe,
//       aiEnabled,
//       serie, // ✅ champ ajouté
//     } = req.body;

//     const pdfsMetadata = JSON.parse(req.body.pdfsMetadata || "[]");
//     const videosMetadata = JSON.parse(req.body.videos || "[]");

//     const uploadedPdfs = (req.files["pdfs"] || []).map((file, i) => ({
//       ...pdfsMetadata[i],
//       url: `/uploads/chapters/${file.filename}`,
//     }));

//     const mainImage = req.files["imageFile"]?.[0]
//       ? `/uploads/chapters/${req.files["imageFile"][0].filename}`
//       : null;

//     const updatedData = {
//       chapterNumber,
//       title,
//       description,
//       level,
//       classe,
//       serie, // ✅ inclusion dans les données mises à jour
//       aiEnabled: aiEnabled === "true",
//       videos: videosMetadata,
//       pdfs: uploadedPdfs.length > 0 ? uploadedPdfs : undefined,
//     };

//     if (mainImage) updatedData.image = mainImage;

//     const chapter = await Chapter.findByIdAndUpdate(id, updatedData, {
//       new: true,
//     });

//     if (!chapter) {
//       return res.status(404).json({ message: "Chapitre introuvable" });
//     }

//     res.json({ message: "✅ Chapitre mis à jour", chapter });
//   } catch (err) {
//     console.error("Erreur updateChapterById :", err);
//     res.status(500).json({ message: "❌ Erreur serveur" });
//   }
// };




// module.exports = { createChapter, getChaptersByClasseAndSubject, deleteChapterById, updateChapterById  };
