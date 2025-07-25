const multer = require('multer');
const streamifier = require('streamifier');
const cloudinary = require('../config/cloudinary');

// 📦 Stockage temporaire en mémoire
const storage = multer.memoryStorage();
const upload = multer({ storage });

// 📸 Middleware pour le champ 'photo'
const uploadTeacherProfil = upload.single('photo');

// ☁️ Upload vers Cloudinary
const uploadTeacherToCloudinary = (req, res, next) => {
  if (!req.file) return next(); // Aucun fichier ? on passe

  const stream = cloudinary.uploader.upload_stream(
    {
      folder: 'teachers', // 👉 Dossier spécifique
    },
    (error, result) => {
      if (error) {
        console.error('Erreur Cloudinary teacher:', error);
        return res.status(500).json({ message: "Échec de l'upload de la photo de l'enseignant." });
      }

      req.body.photo = result.secure_url; // Injecter le lien Cloudinary
      next();
    }
  );

  streamifier.createReadStream(req.file.buffer).pipe(stream);
};

module.exports = {
  uploadTeacherProfil,
  uploadTeacherToCloudinary,
};
