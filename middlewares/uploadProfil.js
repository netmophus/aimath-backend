// middleware/uploadProfil.js
const multer = require('multer');
const streamifier = require('streamifier');
const cloudinary = require('../config/cloudinary'); // ✅ comme demandé

// 📌 Stocker le fichier temporairement en mémoire
const storage = multer.memoryStorage();
const upload = multer({ storage });

// 📌 Middleware pour gérer le champ 'photo'
const uploadProfil = upload.single('photo');

// 📌 Envoi vers Cloudinary
const uploadToCloudinary = (req, res, next) => {
  if (!req.file) return next(); // Aucun fichier envoyé = on continue

  const stream = cloudinary.uploader.upload_stream(
    {
      folder: 'profils',
    },
    (error, result) => {
      if (error) {
        console.error('Erreur Cloudinary :', error);
        return res.status(500).json({ message: "Échec de l'upload Cloudinary" });
      }

      // Injecter l'URL dans req.body.photo pour la suite
      req.body.photo = result.secure_url;
      next();
    }
  );

  streamifier.createReadStream(req.file.buffer).pipe(stream);
};

module.exports = {
  uploadProfil,
  uploadToCloudinary,
};
