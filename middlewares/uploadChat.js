


const { CloudinaryStorage } = require("multer-storage-cloudinary");
const multer = require("multer");
const cloudinary = require("../config/cloudinary");

const chatStorage = new CloudinaryStorage({
  cloudinary,
  params: async (req, file) => {
    const folder = "chat/files";

    // ✅ Déterminer le type de ressource selon le mimetype
    let resource_type = "auto";
    
    if (file.mimetype.startsWith("image")) {
      resource_type = "image"; // ✅ Images = image
    } else if (file.mimetype.startsWith("video")) {
      resource_type = "video"; // ✅ Vidéos = video
    } else if (file.mimetype.startsWith("audio") || file.mimetype === "audio/webm") {
      resource_type = "video"; // ✅ Audio = video (convention Cloudinary)
    } else if (file.mimetype === "application/pdf") {
      resource_type = "raw"; // ✅ PDF = raw
    }

    console.log("📁 Fichier reçu dans uploadChat :", {
      name: file.originalname,
      mimetype: file.mimetype,
      resource_type: resource_type,
    });
 
    return {
      folder,
      resource_type,
      public_id: `${Date.now()}-${file.originalname}`,
      use_filename: true,
      unique_filename: false,
      allowed_formats: ["jpg", "jpeg", "png", "pdf", "mp3", "mp4", "webm", "ogg", "m4a"],
    };
  },
});

const uploadChat = multer({ storage: chatStorage }).single("file");

module.exports = uploadChat;
