
const axios = require("axios");
const { getOrCreateMonthlyUsage } = require("../utils/getOrCreateMonthlyUsage"); // 👈 à ajouter
// const GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent";

const GEMINI_API_URL ="https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;


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





// pour la route ia/solve pour repondre aux questions textes

const callGemini = async (req, res) => {
  const { input } = req.body;
  if (!input) return res.status(400).json({ message: "Aucun texte fourni." });

  const prompt = getPrompt(input);

  try {
    const usage = await getOrCreateMonthlyUsage(req.user._id);

    // ✅ Vérification de la limite pour les questions TEXTES
    if (usage.iaTextQuestions >= 20) {
      return res.status(403).json({ message: "❌ Limite mensuelle atteinte (20 questions texte IA)." });
    }

    const response = await axios.post(
      `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
      {
        contents: [{ role: "user", parts: [{ text: prompt }] }]
      },
      { headers: { "Content-Type": "application/json" } }
    );

    const result = response.data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!result) return res.status(500).json({ message: "Réponse vide de Gemini." });

    // ✅ Incrémentation du compteur de questions texte
    usage.iaTextQuestions += 1;
    await usage.save();

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

Voici le contenu brut extrait de l'image :

"""
${input}
"""

🎯 Ta mission est d'analyser ce contenu.

1. S'il contient un exercice de mathématiques :
   - Reformule l'exercice **proprement comme dans un manuel scolaire**.
   - Avant chaque réponse, explique **la notion de cours associée** (ex : suite, limite, dérivée…).
   - Résous chaque question **étape par étape**.

2. Important : **Affiche comme dans un livre** :
   - N’utilise pas de LaTeX visible.
   - N’utilise pas d’astérisques ou de balises markdown.
   - Présente le texte avec des titres bien visibles, avec des lignes vides pour aérer.
   - Les formules doivent être lisibles, par exemple :  
     u₀ = 2  
     uₙ₊₁ = (1/2) × uₙ + 3  
     lim uₙ = 6  
     f(x) = x² + 1  

3. Si le texte est illisible ou incohérent, dis-le clairement sans inventer.

🧠 Tu peux utiliser LaTeX en interne pour mieux interpréter les maths, mais **le texte affiché doit être brut, lisible et structuré comme dans un manuel imprimé.**
`;


  try {
    const usage = await getOrCreateMonthlyUsage(req.user._id);
    if (usage.iaQuestions >= 30) {
      return res.status(403).json({ message: "❌ Limite mensuelle atteinte (30 questions IA)." });
    }

    console.log("📤 Prompt envoyé à Gemini :\n", prompt); // 🔍 Affiche le prompt

    const response = await axios.post(
      `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
      {
        contents: [{ role: "user", parts: [{ text: prompt }] }]
      },
      { headers: { "Content-Type": "application/json" } }
    );

    const result = response.data?.candidates?.[0]?.content?.parts?.[0]?.text;

    console.log("✅ Réponse Gemini :", result); // ✅ Affiche le résultat

    if (!result) return res.status(500).json({ message: "Réponse vide de Gemini OCR." });

    usage.iaQuestions += 1;
    await usage.save();

    res.json({ response: result });
  } catch (error) {
    console.error("❌ Erreur Gemini OCR :", error.message);
    console.log("🛑 Détail erreur Gemini :", error.response?.data || error); // détail de l'erreur
    res.status(500).json({ message: "Erreur IA OCR", detail: error.message });
  }
};



const OpenAI = require("openai");

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});





// const callGptTxtPrenuim = async (req, res) => {
//   const { input } = req.body;

//   if (!input) {
//     return res.status(400).json({ message: "Entrée manquante." });
//   }

//   try {

//      // 🔒 Vérification des quotas ici
//     const usage = await getOrCreateMonthlyUsage(req.user._id);
//     if (usage.iaTextQuestions >= 20) {
//       return res.status(403).json({ message: "Limite mensuelle de questions IA atteinte." });
//     }



//     const completion = await openai.chat.completions.create({
//       model: "gpt-4", // GPT-4.0
//       messages: [
//         {
//           role: "system",
//           content: `
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
//     });

//     // ✅ Incrémenter le compteur IA
//     usage.iaTextQuestions += 1;
//     await usage.save();

//     const response = completion.choices[0].message.content;
//     res.json({ response });
//   } catch (err) {
//     console.error("Erreur GPT Premium:", err);
//     res.status(500).json({ message: "Erreur lors de la génération de contenu." });
//   }
// };



// Helper générique : tente plusieurs modèles dans l’ordre donné





// --- Helper robuste : gère max_tokens vs max_completion_tokens et fallback de modèles

// ---- util : convertir ^... en exposants typographiques
const SUPER={'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','+':'⁺','-':'⁻','=':'⁼','(':'⁽',')':'⁾',a:'ᵃ',b:'ᵇ',c:'ᶜ',d:'ᵈ',e:'ᵉ',f:'ᶠ',g:'ᵍ',h:'ʰ',i:'ⁱ',j:'ʲ',k:'ᵏ',l:'ˡ',m:'ᵐ',n:'ⁿ',o:'ᵒ',p:'ᵖ',r:'ʳ',s:'ˢ',t:'ᵗ',u:'ᵘ',v:'ᵛ',w:'ʷ',x:'ˣ',y:'ʸ',z:'ᶻ'};
const toSuperscript = s => (s||'').replace(/[{}\s]/g,'').split('').map(c=>SUPER[c]??c).join('');
function typographizeMath(t=''){
  let out=t;
  out=out.replace(/exp\(([^)]+)\)/gi,(_,a)=>'e'+toSuperscript(a.trim()));
  out=out.replace(/e\s*\^\s*\{?([^}]+)\}?/gi,(_,a)=>'e'+toSuperscript(a));
  out=out.replace(/([A-Za-z])\s*\^\s*\{?([A-Za-z])\}?/g,(_,b,e)=>b+toSuperscript(e));
  out=out.replace(/(\S)\s*\^\s*\{?(-?\d+)\}?/g,(_,b,e)=>b+toSuperscript(e));
  return out;
}





async function askTextWithFallback(openai, messages, {
  maxTokens = 900,
  temperature = 0.4,
  models = ["gpt-5", "gpt-5-mini", "o4-mini", "gpt-4o-mini"],
} = {}) {
  // Essaye un modèle avec le bon paramètre; si le paramètre est "unsupported",
  // on retente en inversant (max_tokens <-> max_completion_tokens)
  const tryOnce = async (model, preferCompletionParam) => {
    const buildPayload = (useCompletionParam) => ({
      model,
      messages,
      temperature,
      ...(useCompletionParam
        ? { max_completion_tokens: maxTokens }
        : { max_tokens: maxTokens }),
    });

    // 1er essai avec préférence donnée
    try {
      const r = await openai.chat.completions.create(buildPayload(preferCompletionParam));
      return (r.choices?.[0]?.message?.content || "").trim();
    } catch (e) {
      const msg = (e?.message || "") + " " + (e?.response?.data?.error?.message || "");
      // Si l’erreur indique que le paramètre est non supporté, on inverse et on retente une fois
      const unsupportedMaxTokens = /Unsupported parameter:\s*'max_tokens'|use 'max_completion_tokens'/i.test(msg);
      const unsupportedMaxCompletion = /Unsupported parameter:\s*'max_completion_tokens'|use 'max_tokens'/i.test(msg);
      if (unsupportedMaxTokens || unsupportedMaxCompletion) {
        const r2 = await openai.chat.completions.create(buildPayload(!preferCompletionParam));
        return (r2.choices?.[0]?.message?.content || "").trim();
      }
      throw e;
    }
  };

  // Heuristique : pour gpt-5*/o4* on préfère max_completion_tokens, sinon max_tokens
  const prefersCompletionParam = (m) => /^gpt-5|^o4/i.test(m);

  let lastErr;
  for (const model of models) {
    try {
      return await tryOnce(model, prefersCompletionParam(model));
    } catch (e) {
      // modèle indisponible ou autre → on tente le suivant
      lastErr = e;
      continue;
    }
  }
  throw lastErr || new Error("Aucun modèle texte disponible.");
}

// --- Ta fonction inchangée de nom : callGptTxtPrenuim
const callGptTxtPrenuim = async (req, res) => {
  const { input } = req.body;
  if (!input) {
    return res.status(400).json({ message: "Entrée manquante." });
  }

  try {
    // 🔒 Quota mensuel premium
    const usage = await getOrCreateMonthlyUsage(req.user._id);
    if (usage.iaTextQuestions >= 20) {
      return res.status(403).json({ message: "Limite mensuelle de questions IA atteinte." });
    }

    // 🎯 Tes règles système (inchangées)
    const systemPrompt = `
Tu es un professeur de mathématiques expérimenté, et tu réponds comme dans un manuel scolaire imprimé (papier), destiné à des élèves du collège jusqu’à l’université.

🎯 Ta mission est de résoudre des exercices ou d’expliquer des notions mathématiques de manière rigoureuse, claire et fluide, comme dans un vrai livre de mathématiques.

Voici les règles STRICTES à suivre :

1. Tu peux utiliser des formules en langage LaTeX, mais tu ne dois JAMAIS utiliser de balises Markdown (\`$\`, \`$$\`) ni d’éléments spécifiques à LaTeX comme \\mathbb, \\frac, \\lim, \\int, \\sum, etc. Tout doit être transformé en notation lisible et naturelle, comme dans un livre.

2. Tous les symboles doivent apparaître dans leur version typographique lisible :
  uₙ, 2³, ∫₀¹ x² dx = ⅓, limₓ→ₐ f(x) = L, f′(x), √2, x⁴ + 3x² − 5,
  Δy/Δx, Σₖ₌₁ⁿ aₖ, ∀, ∈, ⊂, ⊆, ∉, ∅, ℝ, ℕ, ℤ, ℚ, ℂ,
  ∘, ⟦1, n⟧, [a, b], ]a, b[, ∂f/∂x, eˣ, aˣ, etc.

  Dérivées : d(eˣ)/dx = eˣ ; d(aˣ)/dx = aˣ × ln(a)
  Propriétés : eˣ⁺ʸ = eˣ × eʸ ; (aˣ)ʸ = aˣʸ ; aˣ / aʸ = aˣ⁻ʸ

3. Aucun style (gras/italique/listes/puces). Paragraphes complets.
4. Texte fluide, comme un chapitre de manuel.
5. Pas de récurrence sauf si demandé.
6. Écris directement ℝ, limₓ→ₐ, etc. (jamais “on note …”).
7. Clair, concis, bienveillant, pédagogique.

Voici maintenant la question à résoudre :
`.trim();

    const messages = [
      { role: "system", content: systemPrompt },
      { role: "user", content: input },
    ];

    // 🔮 GPT-5 prioritaire, avec fallback et gestion auto du paramètre max_*_tokens
    const text = await askTextWithFallback(openai, messages, {
      maxTokens: 900,
      temperature: 0.4,
      models: ["gpt-5", "gpt-5-mini", "o4-mini", "gpt-4o-mini"],
    });

    // ✅ Incrément du quota après succès
    usage.iaTextQuestions += 1;
    await usage.save();

    // return res.json({ response: text });
    return res.json({ response: typographizeMath(text || "") });

  } catch (err) {
    console.error("Erreur GPT Premium:", err?.response?.data || err.message || err);
    return res.status(500).json({ message: "Erreur lors de la génération de contenu." });
  }
};



module.exports = {
  callGemini,
  callGeminiFromText,
  callGptTxtPrenuim
};




























