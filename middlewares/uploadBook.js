const { CloudinaryStorage } = require('multer-storage-cloudinary');
const multer = require('multer');
const cloudinary = require('../config/cloudinary');

// const storage = new CloudinaryStorage({
//   cloudinary,
//   params: async (req, file) => {
//     const folder = file.fieldname === 'cover' ? 'books/covers' : 'books/pdfs';
//     const resource_type = file.mimetype.startsWith('image') ? 'image' : 'raw';

//     return {
//       folder,
//       resource_type,
//       allowed_formats: ['jpg', 'jpeg', 'png', 'pdf'],
//       use_filename: true,         // ✅ Conserver le nom original
//       unique_filename: false,     // ✅ Pas de nom aléatoire
//     };
//   },
// });


// ✅ Ici on exporte directement le middleware combiné

const storage = new CloudinaryStorage({
  cloudinary,
  params: async (req, file) => {
    const folder = file.fieldname === 'cover' ? 'books/covers' : 'books/pdfs';
    const resource_type = file.mimetype.startsWith('image') ? 'image' : 'raw';

    let filename = file.originalname;

    // ✅ Ajoute l’extension .pdf si manquante
    if (file.fieldname === 'pdf' && !filename.toLowerCase().endsWith('.pdf')) {
      filename += '.pdf';
    }

    return {
      folder,
      resource_type,
      public_id: filename, // ✅ conserve toute l'extension
      use_filename: false, // 🔁 on force manuellement avec public_id
      unique_filename: false,
      allowed_formats: ['jpg', 'jpeg', 'png', 'pdf'],
    };
  },
});




const uploadBook = multer({ storage }).fields([
  { name: 'cover', maxCount: 1 },
  { name: 'pdf', maxCount: 1 },
]);

module.exports = uploadBook;
