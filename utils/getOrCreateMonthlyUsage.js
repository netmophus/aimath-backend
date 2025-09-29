
const MonthlyUsage = require("../models/MonthlyUsage");
const User = require("../models/userModel");
const QuestionLimit = require("../models/QuestionLimit");

const getCurrentPeriod = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`; // ex: "2025-08"
};

const getOrCreateMonthlyUsage = async (userId) => {
  const period = getCurrentPeriod();

  // 1) Récupérer l'utilisateur (champs utiles uniquement)
  const user = await User.findById(userId).select("isSubscribed subscriptionStart subscriptionEnd");
  if (!user) throw new Error("Utilisateur introuvable");

  const now = new Date();
  const start = user.subscriptionStart ? new Date(user.subscriptionStart) : null;
  const end   = user.subscriptionEnd ? new Date(user.subscriptionEnd) : null;

  // 2) Vérifier la validité de la souscription
  const isValidSubscription = Boolean(
    user.isSubscribed && start && end && now >= start && now <= end
  );

  // 3) Souscription expirée → reset user + limites puis erreur
  if (!isValidSubscription) {
    await Promise.all([
      User.findByIdAndUpdate(userId, {
        isSubscribed: false,
        subscriptionStart: null,
        subscriptionEnd: null,
      }),

      // Remet/initialise le compteur de questions
      QuestionLimit.updateOne(
        { user: userId },
        { $set: { count: 0, lastReset: now } },
        { upsert: true }
      ),

      // Remet/initialise les usages du mois courant
      MonthlyUsage.updateOne(
        { user: userId, period },
        {
          $set: {
            booksDownloaded: 0,
            videosWatched: 0,
            iaGptVisionQuestions: 0,
            examsDownloaded: 0,
            examsCorrectionsDownloaded: 0,
            iaTextQuestions: 0,
            iaImageQuestions: 0,

      // 👇 ajoute ceci
            supportRequestsCreated: 0,
            supportRequestsAccepted: 0,
            supportRequestsFinished: 0,
            
          },
        },
        { upsert: true }
      ),
    ]);

    throw new Error("Votre souscription est expirée. Veuillez souscrire à nouveau.");
  }

  // 4) Récupérer ou créer le quota du mois courant
  let usage = await MonthlyUsage.findOne({ user: userId, period });
  if (!usage) {
    usage = await MonthlyUsage.create({ user: userId, period });
  }

  return usage;
};

module.exports = { getOrCreateMonthlyUsage };
