const Tesseract = require("tesseract.js");
// const fs = require("fs");
// const path = require("path");
const sharp = require("sharp");
const axios = require("axios");

const { getOrCreateMonthlyUsage } = require("../utils/getOrCreateMonthlyUsage");
const { callGeminiFromText } = require("../controllers/geminiController"); // ajuste le chemin

const fs = require("fs").promises;
const path = require("path");
const OpenAI = require("openai");

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });


function cleanOcrMathText(text) {
  return text
    .replace(/w\s*=\s*2/g, "u₀ = 2")
    .replace(/Un\+1/g, "u_{n+1}")
    .replace(/\bUn\b/g, "u_n")
    .replace(/\bU1\b/g, "u₁").replace(/\bU2\b/g, "u₂").replace(/\bU3\b/g, "u₃")
    .replace(/uy/g, "u₁").replace(/U»/g, "u₂").replace(/Us/g, "u₃")
    .replace(/1\s+2\b/g, "1/2").replace(/1\s+3\b/g, "1/3")
    .replace(/1\s+4\b/g, "1/4").replace(/1\s+5\b/g, "1/5")
    .replace(/\bl\/2\b/g, "1/2").replace(/I\/2/g, "1/2").replace(/l\/2/g, "1/2")
    .replace(/x2\b/g, "x²").replace(/x3\b/g, "x³")
    .replace(/a2\b/g, "a²").replace(/a3\b/g, "a³")
    .replace(/b2\b/g, "b²").replace(/b3\b/g, "b³")
    .replace(/3n\+1/g, "3^{n+1}").replace(/2n\+1/g, "2^{n+1}")
    .replace(/3n/g, "3^n").replace(/2n/g, "2^n")
    .replace(/V\(/g, "√(").replace(/V\s*(\d+)/g, "√$1").replace(/√\s+/g, "√")
    .replace(/:=|=|==/g, "=").replace(/=\s*=/g, "=")
    .replace(/[\[\{]/g, "(").replace(/[\]\}]/g, ")")
    .replace(/\.+/g, ".").replace(/,,+/g, ",")
    .replace(/—/g, "-").replace(/–/g, "-")
    .replace(/\s{2,}/g, " ")
    .trim();
}

const uploadAndSolveImage = async (req, res) => {

  if (!req.file) {
    return res.status(400).json({ message: "Aucune image reçue." });
  }

  const imagePath = path.join(__dirname, "..", req.file.path);
  const processedPath = path.join(__dirname, "..", "uploads", `processed_${Date.now()}.jpg`);

  console.log("📸 Image reçue :", imagePath);

  try {
    await sharp(imagePath)
      .resize({ width: 1200 })
      .grayscale()
      .normalize()
      .trim()
      .extend({
        top: 20, bottom: 20, left: 20, right: 20,
        background: { r: 255, g: 255, b: 255 }
      })
      .toFile(processedPath);

    fs.unlinkSync(imagePath);

    const langFilePath = path.join(__dirname, "tessdata", "fra.traineddata");
    if (!fs.existsSync(langFilePath)) {
      return res.status(500).json({ message: "Le fichier fra.traineddata est manquant dans le dossier tessdata." });
    }

    const { data: { text } } = await Tesseract.recognize(processedPath, "fra", {
      langPath: path.join(__dirname, "tessdata"),
    });

    console.log("📝 Texte brut OCR :", text);

    const cleanedText = cleanOcrMathText(text);
    console.log("🧹 Texte nettoyé :", cleanedText);

    if (!cleanedText || cleanedText.length < 20 || !/[a-zA-Z0-9]/.test(cleanedText)) {
      return res.status(400).json({
        message: "Image floue ou texte illisible. Essayez de prendre la photo avec un zoom x3, plus de lumière et sans tremblement.",
      });
    }

    // 🔄 Incrémentation image
    const usage = await getOrCreateMonthlyUsage(req.user._id);
    if (usage.iaImageQuestions >= 10) {
      return res.status(403).json({ message: "❌ Limite mensuelle atteinte (10 questions par image IA)." });
    }
    usage.iaImageQuestions += 1;
    await usage.save();

    // ▶️ Appel IA Gemini
    console.log("🧠 Envoi à Gemini...");
    return await callGeminiFromText({ body: { input: cleanedText }, user: req.user }, res);

  } catch (error) {
    console.error("❌ Erreur OCR :", error.message);
    return res.status(500).json({ message: "Erreur lors de l'analyse de l'image." });
  } finally {
    if (fs.existsSync(imagePath)) fs.unlinkSync(imagePath);
    if (fs.existsSync(processedPath)) fs.unlinkSync(processedPath);
  }
};


const callMathpixOCR = async (req, res) => {
  if (!req.file) {
    console.log("❌ Aucune image reçue dans la requête.");
    return res.status(400).json({ message: "Aucune image reçue." });
  }

  const imagePath = path.join(__dirname, "..", req.file.path);
  console.log("📸 Image reçue :", imagePath);

  try {
    const imageBuffer = fs.readFileSync(imagePath);
    const base64Image = `data:image/jpeg;base64,${imageBuffer.toString("base64")}`;
    console.log("🔄 Image convertie en base64, taille :", base64Image.length);

    // Construction de la requête Mathpix
    const options = {
      method: "POST",
      url: "https://api.mathpix.com/v3/text",
      headers: {
        "Content-Type": "application/json",
        app_id: process.env.MATHPIX_APP_ID,
        app_key: process.env.MATHPIX_APP_KEY,
      },
      data: {
        src: base64Image,
        formats: ["text", "data", "latex_styled"],
        data_options: { include_asciimath: true, include_latex: true },
      },
    };

    console.log("📤 Envoi de la requête à Mathpix...");
    const response = await axios(options);
    console.log("✅ Réponse reçue de Mathpix.");

    const extractedText = response.data.text;
    console.log("📝 Texte extrait :", extractedText);

    if (!extractedText || extractedText.trim().length < 10) {
      return res.status(400).json({
        message: "Texte OCR insuffisant. L'image est peut-être floue ou mal éclairée.",
      });
    }

    // 🔄 Mise à jour des quotas
    const usage = await getOrCreateMonthlyUsage(req.user._id);
    if (usage.iaImageQuestions >= 10) {
      return res.status(403).json({ message: "❌ Limite mensuelle atteinte." });
    }
    usage.iaImageQuestions += 1;
    await usage.save();
    console.log("📊 Quotas mis à jour.");

    // ▶️ Appel Gemini avec le texte extrait
    console.log("🧠 Envoi du texte à Gemini...");
    return await callGeminiFromText({ body: { input: extractedText }, user: req.user }, res);

  } catch (error) {
    console.error("❌ Erreur dans le traitement Mathpix :", error?.response?.data || error.message);
    return res.status(500).json({ message: "Erreur lors de l'analyse avec Mathpix." });
  } finally {
    if (fs.existsSync(imagePath)) fs.unlinkSync(imagePath);
  }
};












/**
 * Analyse une image (photo d'exercice) avec GPT-4o Vision
 * Retourne une explication mathématique en LaTeX prêt pour rendu KaTeX.
 */
// const callGptVisionSolve = async (req, res) => {
//   try {
//     // Vérifs basiques
//     if (!req.file) {
//       return res.status(400).json({ message: "Aucune image reçue." });
//     }
//     const userId = req.user?._id;

//     // Lis le fichier uploadé
//     const imgPath = req.file.path;              // ex: uploads/abc.jpg
//     const mime = req.file.mimetype || "image/jpeg";
//     const b64 = await fs.readFile(imgPath, { encoding: "base64" });
//     const dataUri = `data:${mime};base64,${b64}`;

//     // Prompt user facultatif envoyé depuis frontend (texte à côté de l'image)
//     const userPrompt = req.body.prompt?.trim() || "Résous l'exercice présent sur cette image. Explique étape par étape et donne la solution finale. Utilise du LaTeX (\\[...\\]) pour les formules.";

//     // Appel OpenAI Vision
//     const completion = await openai.chat.completions.create({
//   model: "gpt-4o",
//   messages: [
//     {
//       role: "system",
//       content: "Tu es un professeur de mathématiques expérimenté. Réponds comme dans un manuel scolaire imprimé...",
//     },
//     {
//       role: "user",
//       content: [
//         {
//           type: "text",
//           text: `
// Résous l’exercice présent sur cette image.
// Explique étape par étape et donne la solution finale.
// Utilise les notations typographiques naturelles (ex: √2, limₓ→ₐ, ℝ, etc.).
// `.trim()
//         },
//         {
//           type: "image_url",
//           image_url: {
//             url: dataUri, // ex: data:image/jpeg;base64,...
//           }
//         }
//       ]
//     }
//   ],
//   max_tokens: 1000,
//   temperature: 0.3,
// });

//     const answer = completion.choices?.[0]?.message?.content?.trim() || "Pas de réponse.";

//     // Nettoyage fichier uploadé (optionnel mais recommandé)
//     try { await fs.unlink(imgPath); } catch (_) {}

//     return res.json({ response: answer });
//   } catch (err) {
//     console.error("❌ GPT-Vision erreur :", err?.response?.data || err.message || err);
//     return res.status(503).json({
//       message: "Erreur GPT-Vision.",
//       detail: err.message,
//     });
//   }
// };


const callGptVisionSolve = async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: "Aucune image reçue." });
    }

    const userId = req.user?._id;

// 🔄 Vérification quota mensuel
const usage = await getOrCreateMonthlyUsage(userId);
if (usage.iaGptVisionQuestions >= 10) {
  return res.status(403).json({ message: "❌ Limite mensuelle atteinte (Vision)." });
}





    const imgPath = req.file.path;
    const mime = req.file.mimetype || "image/jpeg";
    const b64 = await fs.readFile(imgPath, { encoding: "base64" });
    const dataUri = `data:${mime};base64,${b64}`;

    const userPrompt = `
Résous l'exercice présent sur cette image.

Tu es un professeur de mathématiques expérimenté. Présente la réponse comme dans un manuel scolaire imprimé.

✅ Utilise des symboles typographiques lisibles :
• x², x⁴, √2, ∑ₖ₌₁ⁿ, limₓ→ₐ, uₙ, ∫₀¹, ≤, ≥, ≠, eˣ, etc.
• Pour les fractions : écris −5⁄3 (et non \\frac{-5}{3}).
• N'utilise jamais de \`$\`, \`$$\` ou balises LaTeX.
• Écris les étapes clairement, sans liste à puces, sans titres, comme un texte fluide.
Voici en plus d'autres règles STRICTES à suivre :

1. Tu peux utiliser des formules en langage LaTeX, mais tu ne dois JAMAIS utiliser de balises Markdown (\`$\`, \`$$\`) ni d’éléments spécifiques à LaTeX comme \\mathbb, \\frac, \\lim, \\int, \\sum, etc. Tout doit être transformé en notation lisible et naturelle, comme dans un livre.

2. Tous les symboles doivent apparaître dans leur version typographique lisible :
  uₙ au lieu de u_n

2³ = 8 au lieu de 2^3

∫₀¹ x² dx = ⅓ au lieu de \int_0^1 x^2 dx

limₓ→ₐ f(x) = L au lieu de \lim_{x \to a} f(x)

f′(x) au lieu de f'(x) ou df/dx

√2 au lieu de \sqrt{2}

x⁴ + 3x² − 5 au lieu de x^4 + 3x^2 - 5

∆y/∆x ou dy/dx → utiliser la forme typographique et non d/dx brut

Σₖ₌₁ⁿ aₖ au lieu de \sum_{k=1}^n a_k

∀x ∈ ℝ, ∃y ∈ ℕ… au lieu de \forall x \in \mathbb{R}, \exists y \in \mathbb{N}

x → +∞ au lieu de x \to +\infty

a ≠ b au lieu de a \ne b

a ≤ b et a ≥ b au lieu de a \le b, a \ge b

|x| au lieu de \lvert x \rvert

⊂, ⊆, ∈, ∉, ∅, ℝ, ℕ, ℤ, ℚ, ℂ pour les ensembles usuels

∘ pour la composition de fonctions (ex : f ∘ g)

⟦1, n⟧ pour les intervalles entiers, ou [a, b], ]a, b[ pour les intervalles réels

∂f/∂x pour les dérivées partielles (pas \partial f / \partial x)

eˣ au lieu de exp(x) ou e^x (si le contexte le permet)

Utilise toujours la notation eˣ au lieu de e^x ou exp(x) si le contexte le permet.

Si une constante initiale est présente, écris-la naturellement : a × eˣ (et non a * e^x).

Pour les exponentielles à base quelconque : aˣ au lieu de a^x.

Pour les dérivées :

d(eˣ)/dx = eˣ

d(aˣ)/dx = aˣ × ln(a)

Respecte également les notations naturelles pour les propriétés :

eˣ⁺ʸ = eˣ × eʸ

(aˣ)ʸ = aˣʸ

aˣ / aʸ = aˣ⁻ʸ

 explique clairement chaque formule et propriété, comme dans un cours ou un manuel imprimé.

3. N’utilise JAMAIS de caractères pour faire du style (gras, italique, puces, tirets, deux-points après les titres, etc.).
   - Ne commence jamais une ligne par “-”, “•”, “*”, ou autre.
   - Ne fais pas de “**Suites arithmétiques :**”, ni de titres soulignés.
   - Chaque paragraphe doit être complet, sans liste.

4. Structure ta réponse comme un texte fluide et continu, comme un chapitre de livre : plusieurs phrases liées, bien expliquées, sans liste.

5. Ne fais une démonstration par récurrence que si elle est explicitement demandée dans l’énoncé.

6. Ne dis jamais “on note $\mathbb{N}$” ou “on écrit $\lim_{x \\to a}$”. Tu dois écrire directement : ℕ, uₙ, limₓ→ₐ f(x), etc.

7. Évite les longueurs inutiles. Va à l’essentiel avec clarté et rigueur. Ton ton doit être bienveillant et pédagogique.

Termine par la solution finale proprement.
    `.trim();

    const completion = await openai.chat.completions.create({
      model: "gpt-4o-mini", // ou "gpt-4o" si besoin
      messages: [
        {
          role: "system",
          content: "Tu es un professeur de mathématiques rigoureux, répondant comme dans un manuel scolaire imprimé.",
        },
        {
          role: "user",
          content: [
            { type: "text", text: userPrompt },
            { type: "image_url", image_url: { url: dataUri } },
          ],
        },
      ],
      max_tokens: 1000,
      temperature: 0.3,
    });

    const answer = completion.choices?.[0]?.message?.content?.trim() || "Pas de réponse.";

    try { await fs.unlink(imgPath); } catch (_) {}
// ✅ Mise à jour quota
      usage.iaGptVisionQuestions += 1;
      await usage.save();

    return res.json({ response: answer });
  } catch (err) {
    console.error("❌ GPT-Vision erreur :", err?.response?.data || err.message || err);
    return res.status(503).json({
      message: "Erreur GPT-Vision.",
      detail: err.message,
    });
  }
};



module.exports = {
  uploadAndSolveImage,
  callMathpixOCR,
  callGptVisionSolve,
};

