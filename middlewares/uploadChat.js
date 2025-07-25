


const { CloudinaryStorage } = require("multer-storage-cloudinary");
const multer = require("multer");
const cloudinary = require("../config/cloudinary");

const chatStorage = new CloudinaryStorage({
  cloudinary,
  params: async (req, file) => {
    const folder = "chat/files";

    // Déterminer le type de ressource
 
let resource_type = "auto";

if (file.mimetype.startsWith("audio")) {
  resource_type = "video"; // ✅ Cloudinary gère les audios comme des vidéos
}

 console.log("📁 Fichier reçu dans uploadChat :", file);
 
    return {
      folder,
      resource_type,
      public_id: `${Date.now()}-${file.originalname}`,
      use_filename: true,
      unique_filename: false,
      allowed_formats: ["jpg", "jpeg", "png", "pdf", "mp3", "mp4", "webm", "ogg", "m4a"]


    };
  },
});

const uploadChat = multer({ storage: chatStorage }).single("file");

module.exports = uploadChat;
