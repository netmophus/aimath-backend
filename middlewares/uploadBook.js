const { CloudinaryStorage } = require('multer-storage-cloudinary');
const multer = require('multer');
const cloudinary = require('../config/cloudinary');

const storage = new CloudinaryStorage({
  cloudinary,
  params: async (req, file) => {
    const folder = file.fieldname === 'cover' ? 'books/covers' : 'books/pdfs';
    const resource_type = file.mimetype.startsWith('image') ? 'image' : 'raw';

    return {
      folder,
      resource_type,
      allowed_formats: ['jpg', 'jpeg', 'png', 'pdf'],
    };
  },
});

// ✅ Ici on exporte directement le middleware combiné
const uploadBook = multer({ storage }).fields([
  { name: 'cover', maxCount: 1 },
  { name: 'pdf', maxCount: 1 },
]);

module.exports = uploadBook;
