// const axios = require("axios");

// const GEMINI_API_URL =
//   "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent";
// const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

// // 📘 Contrôleur gratuit : donne une piste ou explication
// const callGeminiGratuit = async (req, res) => {
//   const { input } = req.body;

//   if (!input) return res.status(400).json({ message: "Aucun texte fourni." });

//   // const prompt = `Explique simplement ou donne une piste de réflexion pour cette question mathématique : ${input}.`;

//   try {



//     const prompt = `
// Tu es un professeur de mathématiques s’adressant à des élèves .

// Tu dois répondre avec des **formules standard lisibles**, comme celles que l’on trouve dans les **livres de mathématiques**. N'utilise **pas** de LaTeX, **pas de balises HTML**, **pas de code informatique**.

// ✅ Exemples attendus :
// - uₙ = 2n
// - uₙ₊₁ = uₙ + 3
// - ∫₀¹ x² dx = 1/3
// - S = π × r²

// ❌ Ne réponds **jamais** avec du LaTeX ($...$ ou $$...$$), ni avec du code ou des balises <sup> <sub>.

// Ta réponse doit être claire, simple, avec des **phrases pédagogiques** et des **formules mathématiques classiques**.

// Maintenant, explique ou donne une piste de réflexion pour cette question : ${input}
// `;



//     const response = await axios.post(
//       `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
//       {
//         contents: [
//           {
//             role: "user",
//             parts: [{ text: prompt }],
//           },
//         ],
//       },
//       { headers: { "Content-Type": "application/json" } }
//     );

//     const result = response.data?.candidates?.[0]?.content?.parts?.[0]?.text;
//     if (!result) return res.status(500).json({ message: "Réponse vide de Gemini." });

//     res.json({ response: result });
//   } catch (error) {
//     console.error("❌ Erreur IA gratuite :", error.message);
//     res.status(500).json({ message: "Erreur IA gratuite", detail: error.message });
//   }
// };

// module.exports = { callGeminiGratuit };





const axios = require("axios");
const QuestionLimit = require("../models/QuestionLimit");

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

// 📘 Contrôleur principal
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
- N'utilise jamais LaTeX (pas de \`$\`, \`$$\`, \`\\int\`, etc.)
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
- $u_n = 2n$
- <sub>n</sub>
- \\int_a^b f(x) dx

💡 Ta réponse doit être claire, pédagogique, et utiliser des caractères classiques ou Unicode, comme “∫”, “π”, “²”, etc.

Maintenant, explique ou donne une piste de réflexion pour cette question : ${input}

❌ Tu dois ignorer toute question qui ne concerne pas les mathématiques (calcul, fonctions, dérivées, intégrales, limites, suites, géométrie, etc.).

❗ Si la question n’est **pas mathématique**, tu dois simplement répondre :
“⛔ Désolé, je ne traite que des questions de mathématiques.”



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

module.exports = { callGeminiGratuit };
