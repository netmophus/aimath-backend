// testGeminiKey.js
const axios = require("axios");
require("dotenv").config();

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

if (!GEMINI_API_KEY) {
  console.error("❌ Clé API manquante dans le fichier .env");
  process.exit(1);
}

const run = async () => {
  try {
    const res = await axios.get(
      `https://generativelanguage.googleapis.com/v1beta/models?key=${GEMINI_API_KEY}`
    );

    console.log("✅ Clé API valide. Modèles disponibles :\n");
    res.data.models.forEach((model, index) => {
      console.log(`${index + 1}. ${model.name}`);
    });
  } catch (err) {
    console.error("❌ Erreur :", err.response?.data || err.message);
  }
};

run();
