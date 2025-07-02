const { OpenAI } = require("openai");
const { callGeminiFromText } = require("./geminiController");

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const explainConcept = async (req, res) => {
  const { input } = req.body;

  try {
    const chat = await openai.chat.completions.create({
      model: "gpt-3.5-turbo",
      messages: [
        {
          role: "system",
          content: "Tu es un professeur de mathématiques clair et pédagogue. Donne des explications simples et accessibles.",
        },
        {
          role: "user",
          content: `Explique à un élève : "${input}". Fais un rappel du cours et des concepts liés.`,
        },
      ],
      temperature: 0.7,
    });

    res.json({ response: chat.choices[0].message.content });
  } catch (error) {
    console.error("❌ Erreur IA :", error.message);
    res.status(500).json({ message: "Erreur IA" });
  }
};

const solveExercise = async (req, res) => {
  const { input } = req.body;

  try {
    const chat = await openai.chat.completions.create({
      model: "gpt-3.5-turbo",
      messages: [
        {
          role: "system",
          content: "Tu es un professeur de mathématiques. Résous les exercices avec des étapes claires et pédagogiques.",
        },
        {
          role: "user",
          content: `Résous cet exercice : "${input}". Détaille chaque étape clairement.`,
        },
      ],
      temperature: 0.7,
    });

    res.json({ response: chat.choices[0].message.content });
  } catch (error) {
    console.error("❌ Erreur IA :", error.message);
    res.status(500).json({ message: "Erreur IA" });
  }
};



const helpIA = async (req, res) => {
  const { input } = req.body;

  const prompt = `
Tu es un professeur de mathématiques en Terminale C. Rédige ta réponse comme si tu t'adressais à un élève.

**Consignes strictes de format :**
✅ Écris les formules avec des caractères Unicode :
- u₀, u₁, u₂, uₙ, uₙ₊₁
- x², x³, aⁿ
- lim(n→∞)

❌ Ne jamais utiliser de balises HTML (<sub>, <sup>, <strong>, etc.)

✅ Utilise des titres en gras avec deux étoiles (**Titre**)

✅ Fais des paragraphes courts, bien aérés.

✅ Ajoute toujours un exemple calculé clairement étape par étape.

Voici la question de l'élève :
"${input}"
`;

  // Appelle Gemini avec ce prompt structuré
  req.body.input = prompt;
  return callGeminiFromText(req, res);
};



module.exports = { explainConcept, solveExercise , helpIA};
