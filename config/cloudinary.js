// config/cloudinary.js
const dotenv = require("dotenv");
dotenv.config(); // ✅ à mettre en tout premier

const cloudinary = require("cloudinary").v2;

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
  //  timeout: 60000, // ⏱️ 60 secondes
});

module.exports = cloudinary;

