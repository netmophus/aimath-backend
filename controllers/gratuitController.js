
const axios = require("axios");
const QuestionLimit = require("../models/QuestionLimit");
const Book = require("../models/bookModel");
const Exam = require("../models/Exam");
const Video = require("../models/videoModel");
const OpenAI = require("openai");



const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});


// Exemple: import OpenAI SDK quelque part au top de ton fichier
// import OpenAI from "openai";
// const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const MODEL_ID = process.env.OPENAI_MODEL_ID || "gpt-4o-mini"; // <= remplaçable par "o4-mini"


const callGTPTextGratuit = async (req, res) => {
  try {
    const { input } = req.body;
    const userId = req.user._id;
    const maxTests = 5;
    const today = new Date();

    // ⛔ Vérifs basiques
    if (!input || input.trim().length === 0) {
      return res.status(400).json({ message: "Le message est vide." });
    }
    if (input.length > 300) {
      return res.status(400).json({ message: "Votre question est trop longue. Veuillez la raccourcir." });
    }

    // 🔄 Limites mensuelles
    let limit = await QuestionLimit.findOne({ user: userId });
    const isNewMonth =
      limit &&
      (today.getMonth() !== new Date(limit.lastReset).getMonth() ||
        today.getFullYear() !== new Date(limit.lastReset).getFullYear());

    if (limit && !isNewMonth && limit.count >= maxTests) {
      return res.status(403).json({
        message: "Vous avez atteint la limite de 5 questions gratuites ce mois-ci.",
        remaining: 0,
      });
    }

    // 🔮 Appel OpenAI (GPT-4o-mini)
    const completion = await openai.chat.completions.create({
      model: MODEL_ID, // "gpt-4o-mini" ou "o4-mini"
      temperature: 0.35,      // un peu plus stable pour les maths
      max_tokens: 900,        // laisse de la marge à la réponse
      messages: [
        {
          role: "system",
          content: `
Tu es un professeur de mathématiques expérimenté, et tu réponds comme dans un manuel scolaire imprimé (papier), destiné à des élèves du collège jusqu’à l’université.

🎯 Ta mission est de résoudre des exercices ou d’expliquer des notions mathématiques de manière rigoureuse, claire et fluide, comme dans un vrai livre de mathématiques.

Voici les règles STRICTES à suivre :

1. Tu peux utiliser des formules en langage LaTeX, mais tu ne dois JAMAIS utiliser de balises Markdown (\`$\`, \`$$\`) ni d’éléments spécifiques à LaTeX comme \\mathbb, \\frac, \\lim, \\int, \\sum, etc. Tout doit être transformé en notation lisible et naturelle, comme dans un livre.

2. Tous les symboles doivent apparaître dans leur version typographique lisible :
uₙ ; 2³ ; ∫₀¹ x² dx ; limₓ→ₐ f(x) ; f′(x) ; √2 ; x⁴ + 3x² − 5 ; ∆y/∆x ; Σₖ₌₁ⁿ aₖ ; ∀x ∈ ℝ, ∃y ∈ ℕ ; x → +∞ ; a ≠ b ; a ≤ b ; |x| ; ⊂ ⊆ ∈ ∉ ∅ ℝ ℕ ℤ ℚ ℂ ; ∘ ; ⟦1, n⟧ ; [a, b], ]a, b[ ; ∂f/∂x ; eˣ ; aˣ.
Toujours privilégier eˣ, aˣ. Dérivées: d(eˣ)/dx = eˣ ; d(aˣ)/dx = aˣ × ln(a).
Propriétés: eˣ⁺ʸ = eˣ × eʸ ; (aˣ)ʸ = aˣʸ ; aˣ / aʸ = aˣ⁻ʸ.

3. Pas de listes, pas de puces, pas de gras. Texte continu, clair, pédagogique, comme dans un chapitre.

4. Pas de récurrence sauf si demandée explicitement.

5. N’écris jamais “on note \\mathbb{R}” ; écris directement ℝ, uₙ, limₓ→ₐ f(x), etc.

6. Va à l’essentiel, reste bienveillant et rigoureux.
          `.trim(),
        },
        { role: "user", content: input },
      ],
    });

    const fullResponse = completion?.choices?.[0]?.message?.content?.trim() || "Désolé, aucune réponse.";
    // ⚠️ On NE coupe plus la réponse (on enlève l'ancien 'trimmedResponse')

    // ✅ Incrémenter seulement après succès
    if (!limit) {
      await QuestionLimit.create({ user: userId, count: 1, lastReset: today });
    } else if (isNewMonth) {
      limit.count = 1;
      limit.lastReset = today;
      await limit.save();
    } else {
      limit.count += 1;
      await limit.save();
    }

    const updatedLimit = await QuestionLimit.findOne({ user: userId });
    const remaining = Math.max(0, maxTests - (updatedLimit?.count || 0));

    return res.json({ response: fullResponse, remaining });
  } catch (error) {
    console.error("Erreur GPT :", error?.response?.data || error.message);
    return res.status(500).json({ error: "Erreur serveur ou OpenAI" });
  }
};







// const callGTPTextGratuit = async (req, res) => {
//   try {
   

//     const { input } = req.body;
//     const userId = req.user._id;
//     const maxTests = 5;
//     const today = new Date();

//     // ⛔ Vérifications
//     if (!input || input.trim().length === 0) {
//       return res.status(400).json({ message: "Le message est vide." });
//     }

//     if (input.length > 300) {
//       return res.status(400).json({ message: "Votre question est trop longue. Veuillez la raccourcir." });
//     }

//     // 🔄 Récupérer les infos de limite
//     let limit = await QuestionLimit.findOne({ user: userId });
//     const isNewMonth = limit &&
//       (today.getMonth() !== new Date(limit.lastReset).getMonth() ||
//        today.getFullYear() !== new Date(limit.lastReset).getFullYear());

//        console.log("📊 État compteur avant requête :", {
//   count: limit?.count,
//   lastReset: limit?.lastReset,
// });


//     if (limit && !isNewMonth && limit.count >= maxTests) {
//       return res.status(403).json({
//         message: "Vous avez atteint la limite de 5 questions gratuites ce mois-ci.",
//         remaining: 0,
//       });
//     }

//     // 🔮 Appel OpenAI
//     const completion = await openai.chat.completions.create({
//       model: "gpt-3.5-turbo",
//       messages: [
//         {
//           role: "system",
//          content: `
// Tu es un professeur de mathématiques expérimenté, et tu réponds comme dans un manuel scolaire imprimé (papier), destiné à des élèves du collège jusqu’à l’université.

// 🎯 Ta mission est de résoudre des exercices ou d’expliquer des notions mathématiques de manière rigoureuse, claire et fluide, comme dans un vrai livre de mathématiques.

// Voici les règles STRICTES à suivre :

// 1. Tu peux utiliser des formules en langage LaTeX, mais tu ne dois JAMAIS utiliser de balises Markdown (\`$\`, \`$$\`) ni d’éléments spécifiques à LaTeX comme \\mathbb, \\frac, \\lim, \\int, \\sum, etc. Tout doit être transformé en notation lisible et naturelle, comme dans un livre.

// 2. Tous les symboles doivent apparaître dans leur version typographique lisible :
//   uₙ au lieu de u_n

// 2³ = 8 au lieu de 2^3

// ∫₀¹ x² dx = ⅓ au lieu de \int_0^1 x^2 dx

// limₓ→ₐ f(x) = L au lieu de \lim_{x \to a} f(x)

// f′(x) au lieu de f'(x) ou df/dx

// √2 au lieu de \sqrt{2}

// x⁴ + 3x² − 5 au lieu de x^4 + 3x^2 - 5

// ∆y/∆x ou dy/dx → utiliser la forme typographique et non d/dx brut

// Σₖ₌₁ⁿ aₖ au lieu de \sum_{k=1}^n a_k

// ∀x ∈ ℝ, ∃y ∈ ℕ… au lieu de \forall x \in \mathbb{R}, \exists y \in \mathbb{N}

// x → +∞ au lieu de x \to +\infty

// a ≠ b au lieu de a \ne b

// a ≤ b et a ≥ b au lieu de a \le b, a \ge b

// |x| au lieu de \lvert x \rvert

// ⊂, ⊆, ∈, ∉, ∅, ℝ, ℕ, ℤ, ℚ, ℂ pour les ensembles usuels

// ∘ pour la composition de fonctions (ex : f ∘ g)

// ⟦1, n⟧ pour les intervalles entiers, ou [a, b], ]a, b[ pour les intervalles réels

// ∂f/∂x pour les dérivées partielles (pas \partial f / \partial x)

// eˣ au lieu de exp(x) ou e^x (si le contexte le permet)

// Utilise toujours la notation eˣ au lieu de e^x ou exp(x) si le contexte le permet.

// Si une constante initiale est présente, écris-la naturellement : a × eˣ (et non a * e^x).

// Pour les exponentielles à base quelconque : aˣ au lieu de a^x.

// Pour les dérivées :

// d(eˣ)/dx = eˣ

// d(aˣ)/dx = aˣ × ln(a)

// Respecte également les notations naturelles pour les propriétés :

// eˣ⁺ʸ = eˣ × eʸ

// (aˣ)ʸ = aˣʸ

// aˣ / aʸ = aˣ⁻ʸ

//  explique clairement chaque formule et propriété, comme dans un cours ou un manuel imprimé.

// 3. N’utilise JAMAIS de caractères pour faire du style (gras, italique, puces, tirets, deux-points après les titres, etc.).
//    - Ne commence jamais une ligne par “-”, “•”, “*”, ou autre.
//    - Ne fais pas de “**Suites arithmétiques :**”, ni de titres soulignés.
//    - Chaque paragraphe doit être complet, sans liste.

// 4. Structure ta réponse comme un texte fluide et continu, comme un chapitre de livre : plusieurs phrases liées, bien expliquées, sans liste.

// 5. Ne fais une démonstration par récurrence que si elle est explicitement demandée dans l’énoncé.

// 6. Ne dis jamais “on note $\mathbb{N}$” ou “on écrit $\lim_{x \\to a}$”. Tu dois écrire directement : ℕ, uₙ, limₓ→ₐ f(x), etc.

// 7. Évite les longueurs inutiles. Va à l’essentiel avec clarté et rigueur. Ton ton doit être bienveillant et pédagogique.

// Voici maintenant la question à résoudre :
// `,

//         },
//         {
//           role: "user",
//           content: input,
//         },
//       ],
//       max_tokens: 500,
//       temperature: 0.7,
//     });

//     const fullResponse = completion.choices[0].message.content;
//     const trimmedResponse = fullResponse.split("\n").slice(0, 10).join("\n");

//     // ✅ Incrémenter seulement après succès
//     if (!limit) {
//       await QuestionLimit.create({ user: userId, count: 1, lastReset: today });
//     } else if (isNewMonth) {
//       limit.count = 1;
//       limit.lastReset = today;
//       await limit.save();
//     } else {
//       limit.count += 1;
//       await limit.save();
//     }

//     const updatedLimit = await QuestionLimit.findOne({ user: userId });
//     const remaining = maxTests - updatedLimit.count;

//     res.json({ response: trimmedResponse, remaining });
//   } catch (error) {
//     console.error("Erreur GPT :", error.message);
//     res.status(500).json({ error: "Erreur serveur ou OpenAI" });
//   }
// };






const GEMINI_API_URL =
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent";
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

// 🧼 Nettoyage : transforme <sub>...</sub> et <sup>...</sup> en Unicode propre
function cleanHtmlTags(text) {
  return text
    .replace(/<sub>a<\/sub>/g, 'ₐ')
    .replace(/<sub>b<\/sub>/g, 'ᵦ')
    .replace(/<sub>0<\/sub>/g, '₀')
    .replace(/<sub>1<\/sub>/g, '₁')
    .replace(/<sub>2<\/sub>/g, '₂')
    .replace(/<sub>n<\/sub>/g, 'ₙ')

    .replace(/<sup>a<\/sup>/g, 'ᵃ')
    .replace(/<sup>b<\/sup>/g, 'ᵇ')
    .replace(/<sup>2<\/sup>/g, '²')
    .replace(/<sup>n<\/sup>/g, 'ⁿ')
    .replace(/<sup>x<\/sup>/g, 'ˣ')
    .replace(/<sup>\+<\/sup>/g, '⁺')

    .replace(/<\/?[^>]+(>|$)/g, ''); // nettoie toute autre balise
}

// 📘 pour la route Gratuit 
const callGeminiGratuit = async (req, res) => {
  const { input } = req.body;
  const userId = req.user?._id;

  if (!input) return res.status(400).json({ message: "Aucune question fournie." });
  if (!userId) return res.status(401).json({ message: "Utilisateur non authentifié." });

  try {
    // Vérifie la limite de 3 questions
    let record = await QuestionLimit.findOne({ user: userId });

    if (record && record.count >= 3) {
      return res.status(403).json({
        message: "❌ Vous avez atteint la limite gratuite de 3 questions. Veuillez vous abonner.",
        redirectTo: "/pricing",
      });
    }

const prompt = `
Tu es un professeur de mathématiques s’adressant à des élèves du secondaire.

🛑 Interdiction formelle :
- N'utilise jamais LaTeX (pas de \`\\$\`, \`\\$\\$\`, \`\\\\int\`, etc.)
- N'utilise pas les balises HTML (<sub>, <sup>, etc.)
- N'utilise aucun format informatique ou balisage.

✅ Ta réponse doit utiliser uniquement :
- Du texte pur
- Des formules classiques comme dans les manuels scolaires

📘 Exemple attendu :
- uₙ = 2n
- uₙ₊₁ = uₙ + 3
- ∫ₐᵇ f(x) dx
- S = π × r²

❌ Exemples interdits :
- \\$u_n = 2n\\$
- <sub>n</sub>
- \\\\int_a^b f(x) dx

💡 Ta réponse doit être claire, pédagogique, précise et facile à comprendre pour un élève de collège ou de lycée.

✍️ Très important :  
Tu dois rédiger en bon français, sans aucune faute d’orthographe, de grammaire ni de frappe. Les phrases doivent être bien structurées et compréhensibles. Le texte doit être lisible comme dans un manuel scolaire imprimé.

❌ Tu dois ignorer toute question qui ne concerne pas les mathématiques (calcul, fonctions, dérivées, intégrales, limites, suites, géométrie, etc.).

❗ Si la question n’est **pas mathématique**, tu dois simplement répondre :
“⛔ Désolé, je ne traite que des questions de mathématiques.”

Maintenant, explique ou donne une piste de réflexion pour cette question : ${input}
`;


    const response = await axios.post(
      `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
      {
        contents: [{ role: "user", parts: [{ text: prompt }] }],
      },
      { headers: { "Content-Type": "application/json" } }
    );

    const result = response.data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!result) return res.status(500).json({ message: "Réponse vide de Gemini." });

    // Nettoyage HTML
    const cleaned = cleanHtmlTags(result);

    // Incrémente le compteur
    if (record) {
      record.count += 1;
      await record.save();
    } else {
      await QuestionLimit.create({ user: userId, count: 1 });
    }

    res.json({ response: cleaned });
  } catch (error) {
    console.error("❌ Erreur IA gratuite :", error.response?.data || error.message);
    res.status(503).json({ message: "Erreur IA gratuite", detail: error.message });
  }
};















// 📖 Visualisation d’un livre gratuit
const viewGratuitBook = async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);

    if (!book) {
      return res.status(404).json({ message: "Livre non trouvé." });
    }

    if (book.badge !== "gratuit") {
      return res.status(403).json({ message: "Ce livre n'est pas gratuit." });
    }

    // Incrémenter le compteur de visualisation
    book.viewCount = (book.viewCount || 0) + 1;
    await book.save();

    res.json({ viewUrl: book.fileUrl });
  } catch (err) {
    res.status(500).json({ message: "Erreur serveur lors de la visualisation." });
  }
};

// 📥 Téléchargement d’un livre gratuit
const downloadGratuitBook = async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);

    if (!book) {
      return res.status(404).json({ message: "Livre non trouvé." });
    }

    if (book.badge !== "gratuit") {
      return res.status(403).json({ message: "Ce livre n'est pas gratuit." });
    }

    // Incrémenter le compteur de téléchargement
    book.downloadCount = (book.downloadCount || 0) + 1;
    await book.save();

    res.json({ downloadUrl: book.fileUrl });
  } catch (err) {
    res.status(500).json({ message: "Erreur serveur lors du téléchargement." });
  }
};




// ✅ Télécharger un sujet gratuit + incrément
const getGratuitExamSubjectUrl = async (req, res) => {
  try {
    const exam = await Exam.findById(req.params.id);
    if (!exam) return res.status(404).json({ message: "Examen introuvable" });

    if (exam.badge !== "gratuit") {
      return res.status(403).json({ message: "Accès réservé aux examens gratuits" });
    }

    // ➕ Incrémenter le compteur
    exam.subjectDownloadCount += 1;
    await exam.save();

    res.json({ subjectUrl: exam.subjectUrl });
  } catch (err) {
    res.status(500).json({ message: "Erreur lors de l'accès au sujet" });
  }
};

// ✅ Télécharger une correction gratuite + incrément
const getGratuitExamCorrectionUrl = async (req, res) => {
  try {
    const exam = await Exam.findById(req.params.id);
    if (!exam) return res.status(404).json({ message: "Examen introuvable" });

    if (exam.badge !== "gratuit") {
      return res.status(403).json({ message: "Accès réservé aux examens gratuits" });
    }

    // ➕ Incrémenter le compteur
    exam.correctionDownloadCount += 1;
    await exam.save();

    res.json({ correctionUrl: exam.correctionUrl });
  } catch (err) {
    res.status(500).json({ message: "Erreur lors de l'accès à la correction" });
  }
};





const getGratuitVideoUrl = async (req, res) => {
  const video = await Video.findById(req.params.id);
  if (!video) return res.status(404).json({ message: "Vidéo introuvable" });

  if (video.badge !== "gratuit") {
    return res.status(403).json({ message: "Accès réservé aux vidéos gratuites" });
  }

  // ✅ Incrémenter compteur (si besoin)
  video.viewCount = (video.viewCount || 0) + 1;
  await video.save();

  res.json({ videoUrl: video.videoUrl });
};



// ✅ Afficher tous les livres
const getAllBooks = async (req, res) => {
  try {
    const books = await Book.find().sort({ createdAt: -1 });
    res.json(books);
  } catch (err) {
    res.status(500).json({ message: "❌ Erreur lors de la récupération des livres." });
  }
};

// ✅ Afficher un seul livre par ID
const getBookById = async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);
    if (!book) return res.status(404).json({ message: "📘 Livre non trouvé." });

    res.json(book);
  } catch (err) {
    res.status(500).json({ message: "❌ Erreur lors de la récupération du livre." });
  }
};



module.exports = {
   callGeminiGratuit,
   callGTPTextGratuit,
  viewGratuitBook,
  downloadGratuitBook,
  getGratuitExamSubjectUrl,
  getGratuitExamCorrectionUrl,
  getGratuitVideoUrl,
  getAllBooks,
  getBookById,


};


