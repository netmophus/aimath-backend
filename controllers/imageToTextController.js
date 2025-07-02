

const Tesseract = require("tesseract.js");
const fs = require("fs");
const path = require("path");
const { callGeminiFromText } = require("./geminiController");

const uploadAndSolveImage = async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ message: "Aucune image reçue." });
  }

  const imagePath = path.join(__dirname, "..", req.file.path);

  try {
    // const { data: { text } } = await Tesseract.recognize(imagePath, "fra");
   
const { data: { text } } = await Tesseract.recognize(imagePath, "fra", {
  langPath: path.join(__dirname, "tessdata") // 👈 vers controllers/tessdata/
});


// ✅ Ajoute cette ligne ici
console.log("📄 Texte extrait :", text);

    fs.unlinkSync(imagePath);

    if (!text || text.trim().length < 5) {
      return res.status(400).json({ message: "Texte illisible dans l'image." });
    }


      // ✅ Nettoyage des erreurs courantes d'OCR
    const cleanedText = text
      .replace(/w\s*=\s*2/g, "u₀ = 2")
      .replace(/Un\+1/g, "u_{n+1}")
      .replace(/Un/g, "u_n")
      .replace(/uy/g, "u₁")
      .replace(/U»/g, "u₂")
      .replace(/Us/g, "u₃")
      .replace(/768"\s*=\s*1\)/g, "(3^{n+1} - 1)") // tentative de correction de la mauvaise formule
      .replace(/1\s+1/g, "1/2") // fraction mal reconnue

    console.log("🧹 Texte nettoyé :", cleanedText);


    req.body.input = text; // pas de nettoyage
    return callGeminiFromText(req, res);
  } catch (error) {
    console.error("❌ Erreur OCR :", error.message);
    return res.status(500).json({ message: "Erreur lors de l'analyse de l'image." });
  }
};

module.exports = { uploadAndSolveImage };


