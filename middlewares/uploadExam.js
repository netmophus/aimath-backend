// const { CloudinaryStorage } = require('multer-storage-cloudinary');
// const multer = require('multer');
// const cloudinary = require('../config/cloudinary');

// const storage = new CloudinaryStorage({
//   cloudinary,
//   params: async (req, file) => {
//     const folder = file.fieldname === 'cover' ? 'exams/covers' : 'exams/pdfs';
//     const resource_type = file.mimetype.startsWith('image') ? 'image' : 'raw';

//     let filename = file.originalname;

//     // ✅ Si c’est un fichier sujet ou correction sans .pdf, on ajoute l’extension
//     if (
//       (file.fieldname === 'subject' || file.fieldname === 'correction') &&
//       !filename.toLowerCase().endsWith('.pdf')
//     ) {
//       filename += '.pdf';
//     }

//     return {
//       folder,
//       resource_type,
//       public_id: filename,       // ✅ on garde l’extension exacte
//       use_filename: false,       // ❌ désactivé car on utilise public_id
//       unique_filename: false,    // ❌ pas de nom aléatoire
//       allowed_formats: ['jpg', 'jpeg', 'png', 'pdf'],
//     };
//   },
// });

// const uploadExam = multer({ storage }).fields([
//   { name: 'cover', maxCount: 1 },
//   { name: 'subject', maxCount: 1 },
//   { name: 'correction', maxCount: 1 },
// ]);

// module.exports = uploadExam;






const { CloudinaryStorage } = require('multer-storage-cloudinary');
const multer = require('multer');
const cloudinary = require('../config/cloudinary');

const storage = new CloudinaryStorage({
  cloudinary,
  params: async (req, file) => {
    const folder = file.fieldname === 'cover' ? 'exams/covers' : 'exams/pdfs';
    const resource_type = file.mimetype.startsWith('image') ? 'image' : 'raw';

    let filename = file.originalname;

    // ✅ Si c’est un fichier sujet ou correction sans extension .pdf, on ajoute
    if (
      (file.fieldname === 'subject' || file.fieldname === 'correction') &&
      !filename.toLowerCase().endsWith('.pdf')
    ) {
      filename += '.pdf';
    }

    return {
      folder,
      resource_type,
      public_id: filename,        // Nom tel quel avec extension
      use_filename: false,        // Empêche Cloudinary d’ignorer public_id
      unique_filename: false,     // Pas de nom aléatoire
      allowed_formats: ['jpg', 'jpeg', 'png', 'pdf'], // Formats autorisés
    };
  },
});

// 📥 Multer avec 3 champs (cover, subject, correction)
const uploadExam = multer({ storage }).fields([
  { name: 'cover', maxCount: 1 },
  { name: 'subject', maxCount: 1 },
  { name: 'correction', maxCount: 1 },
]);

module.exports = uploadExam;
