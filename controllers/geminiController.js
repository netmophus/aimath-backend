


// const axios = require("axios");
// const fs = require("fs");
// const path = require("path");

// const GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent";
// const GEMINI_API_KEY = process.env.GEMINI_API_KEY;





// const programmeContext = `
// Tu es un professeur de mathématiques.
// Tu dois répondre avec des formules mathématiques claires, rédigées en LaTeX entre des dollars \`$...$\` ou \`$$...$$\`.

// ✅ Exemple :
// - $u_n = 2n$
// - $u_{n+1} = u_n + 3$

// ❌ N’utilise pas les balises HTML comme <sub>, <sup>.
// `;






// const getPrompt = (input) => {
//   const lowerInput = input.toLowerCase();
//   for (const keyword in keywordsMap) {
//     if (lowerInput.includes(keyword)) {
//       return programmeContext + keywordsMap[keyword];
//     }
//   }




  
//   return (
//     programmeContext +
//     `Résous cet exercice de maths : ${input}. Donne les étapes claires, rigoureuses, et pédagogiques avec les symboles mathématiques classiques (x², →, π, √...). Utilise les balises <strong>...</strong> pour mettre en évidence les titres et étapes.
//     Tu dois répondre avec des formules mathématiques claires, rédigées en LaTeX entre des dollars \`$...$\` (pour une formule dans le texte) ou \`$$...$$\` (pour une formule sur une ligne seule).

// ✅ Exemple de bonne écriture :
// - $u_n = 2n$
// - $u_{n+1} = u_n + 3$
// - $\\int_0^1 x^2 dx = \\frac{1}{3}$

// **IMPORTANT** : Lorsque la consigne demande une démonstration par récurrence d'une formule donnée, **ne remets pas en cause la formule**. Supposons qu'elle est correcte, et effectue la démonstration **pas à pas** en respectant les étapes suivantes :

// - Initialisation
// - Hérédité
// - Conclusion

// Utilise les symboles mathématiques classiques en LaTeX : par exemple $u_n = 2n$, $\\forall n \\in \\mathbb{N}$, etc. Pour les formules, encadre-les avec \`$\` ou \`$$\`.


// ❌ N’utilise pas les balises HTML comme <sub>, <sup>, ni de pseudo-code mathématique.


//     `
//   );
// };

// // ✅ Contrôleur texte manuel
// const callGemini = async (req, res) => {
//   const { input } = req.body;
//   if (!input) return res.status(400).json({ message: "Aucun texte fourni." });

//   const prompt = getPrompt(input);

//   try {
//     const response = await axios.post(
//       `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
//       {
//         contents: [{ role: "user", parts: [{ text: prompt }] }]
//       },
//       { headers: { "Content-Type": "application/json" } }
//     );

//     const result = response.data?.candidates?.[0]?.content?.parts?.[0]?.text;
//     if (!result) return res.status(500).json({ message: "Réponse vide de Gemini." });

//     res.json({ response: result });
//   } catch (error) {
//     console.error("❌ Erreur Gemini :", error.message);
//     res.status(500).json({ message: "Erreur IA", detail: error.message });
//   }
// };






// // ✅ Contrôleur OCR (images)
// const callGeminiFromText = async (req, res) => {
//   const { input } = req.body;
//   if (!input) return res.status(400).json({ message: "Texte manquant pour l'IA." });

// //   const prompt = programmeContext + `Résous cet exercice de maths : ${input}. 
// // Présente la solution complète, étape par étape, avec un langage clair et les balises <strong>...</strong> pour les points importants.`;


// const prompt = `
// Tu vas recevoir un extrait de texte provenant d'une image scannée contenant un exercice de mathématiques.
// Ne te focalise pas sur la forme du texte ou des erreurs de lecture automatique.

// Voici le contenu brut de l'image :

// """
// ${input}
// """

// ➡️ Analyse ce contenu.
// ➡️ Si tu détectes un exercice mathématique (même incomplet ou mal lu), reformule-le proprement puis **résous-le étape par étape**.

// Mets les points importants en <strong>gras</strong>.
// Si le texte est incohérent ou ne contient pas d'exercice, dis-le explicitement.`;




//   try {
//     const response = await axios.post(
//       `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
//       {
//         contents: [{ role: "user", parts: [{ text: prompt }] }]
//       },
//       { headers: { "Content-Type": "application/json" } }
//     );

//     const result = response.data?.candidates?.[0]?.content?.parts?.[0]?.text;
//     if (!result) return res.status(500).json({ message: "Réponse vide de Gemini." });

//     res.json({ response: result });
//   } catch (error) {
//     console.error("❌ Erreur Gemini OCR :", error.message);
//     res.status(500).json({ message: "Erreur IA OCR", detail: error.message });
//   }
// };

// module.exports = {
//   callGemini,
//   callGeminiFromText
// };





const axios = require("axios");

const GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent";
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

// const programmeContext = `
// Tu es un professeur de mathématiques expérimenté, capable d’expliquer avec rigueur et pédagogie tous les sujets, du collège jusqu’à l’université.

// Ta mission est de résoudre des exercices ou d’expliquer des notions de manière claire, rigoureuse et pédagogique, comme dans un manuel scolaire imprimé.

// Règles à respecter :

// - Tu peux utiliser des formules en langage LaTeX si cela facilite la compréhension, mais n’utilise jamais les balises $...$ ou $$...$$. Écris les formules de manière naturelle et lisible, comme dans les livres :
//   uₙ = 2n + 1
//   2³ = 8
//   ∫₀¹ x² dx = ⅓

// - N’utilise jamais les astérisques (*), les symboles Markdown (**gras**, - tirets, etc.) ou tout autre style de mise en forme qui ne correspond pas à l'apparence d’un manuel scolaire.

// - Structure la réponse avec des paragraphes clairs, des phrases complètes, et des sauts de ligne naturels. Aucun titre ou sous-titre artificiel ne doit être inséré.

// - Si une démonstration par récurrence est explicitement demandée dans l’énoncé, ou si l’exercice impose de justifier une formule, alors fais la démonstration en suivant ces étapes :
//   Initialisation
//   Hérédité
//   Conclusion

// - Si ce n’est pas demandé, n’ajoute pas de démonstration par récurrence.

// Tu dois éviter complètement les listes à puces automatiques. Préfère des paragraphes explicatifs en phrases complètes, avec des exemples intégrés naturellement.


// Ton ton doit être bienveillant, ton raisonnement rigoureux, et le vocabulaire adapté au niveau de l’élève concerné (collège, lycée ou université).

// Voici l’exercice à résoudre :
// `;


const programmeContext = `
Tu es un professeur de mathématiques expérimenté, et tu réponds comme dans un manuel scolaire imprimé (papier), destiné à des élèves du collège jusqu’à l’université.

🎯 Ta mission est de résoudre des exercices ou d’expliquer des notions mathématiques de manière rigoureuse, claire et fluide, comme dans un vrai livre de mathématiques.

Voici les règles STRICTES à suivre :

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

Voici maintenant la question à résoudre :
`;



const getPrompt = (input) => {
  return (
    programmeContext +
    `
${input}

Rédige ta réponse comme si tu écrivais dans un manuel de mathématiques imprimé.

Respecte toutes les règles précédentes : pas de Markdown, pas d'astérisques, pas de balises LaTeX visibles. Ta réponse doit être claire, bien structurée, naturelle, comme un vrai professeur.`
  );
};


const callGemini = async (req, res) => {
  const { input } = req.body;
  if (!input) return res.status(400).json({ message: "Aucun texte fourni." });

  const prompt = getPrompt(input);

  try {
    const response = await axios.post(
      `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
      {
        contents: [{ role: "user", parts: [{ text: prompt }] }]
      },
      { headers: { "Content-Type": "application/json" } }
    );

    const result = response.data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!result) return res.status(500).json({ message: "Réponse vide de Gemini." });

    res.json({ response: result });
  } catch (error) {
    console.error("❌ Erreur Gemini :", error.message);
    res.status(500).json({ message: "Erreur IA", detail: error.message });
  }
};

const callGeminiFromText = async (req, res) => {
  const { input } = req.body;
  if (!input) return res.status(400).json({ message: "Texte manquant pour l'IA." });

  const prompt = `
Tu vas recevoir un extrait de texte provenant d'une image scannée contenant un exercice de mathématiques.
Ne te focalise pas sur la forme du texte ou des erreurs de lecture automatique.

Voici le contenu brut de l'image :

"""
${input}
"""

➡️ Analyse ce contenu.
➡️ Si tu détectes un exercice mathématique (même incomplet ou mal lu), reformule-le proprement puis **résous-le étape par étape**.

Mets les points importants en <strong>gras</strong>.
Si le texte est incohérent ou ne contient pas d'exercice, dis-le explicitement.
`;

  try {
    const response = await axios.post(
      `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
      {
        contents: [{ role: "user", parts: [{ text: prompt }] }]
      },
      { headers: { "Content-Type": "application/json" } }
    );

    const result = response.data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!result) return res.status(500).json({ message: "Réponse vide de Gemini OCR." });

    res.json({ response: result });
  } catch (error) {
    console.error("❌ Erreur Gemini OCR :", error.message);
    res.status(500).json({ message: "Erreur IA OCR", detail: error.message });
  }
};

module.exports = {
  callGemini,
  callGeminiFromText
};




























