
// const MonthlyUsage = require("../models/MonthlyUsage");
// const User = require("../models/userModel"); // ✅ à importer

// const getCurrentPeriod = () => {
//   const now = new Date();
//   return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
// };

// const getOrCreateMonthlyUsage = async (userId) => {
//   const period = getCurrentPeriod();

//   // ✅ Étape 1 : récupérer l'utilisateur
//   const user = await User.findById(userId);
//   if (!user) {
//     throw new Error("Utilisateur introuvable");
//   }

//   // ✅ Étape 2 : vérifier la validité de la souscription

//   console.log("🔍 Vérification souscription :", {
//   isSubscribed: user.isSubscribed,
//   start: user.subscriptionStart,
//   end: user.subscriptionEnd,
//   now: now,
// });

//   const now = new Date();
//   const isValidSubscription =
//     user.isSubscribed &&
//     user.subscriptionStart &&
//     user.subscriptionEnd &&
//     now >= user.subscriptionStart &&
//     now <= user.subscriptionEnd;

//   if (!isValidSubscription) {
//     throw new Error("Vous n'avez pas de souscription active.");
//   }

//   // ✅ Étape 3 : vérifier ou créer le quota du mois
//   let usage = await MonthlyUsage.findOne({ user: userId, period });

//   if (!usage) {
//     usage = await MonthlyUsage.create({ user: userId, period });
//   }

//   return usage;
// };

// module.exports = { getOrCreateMonthlyUsage };




const MonthlyUsage = require("../models/MonthlyUsage");
const User = require("../models/userModel");

const getCurrentPeriod = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
};

const getOrCreateMonthlyUsage = async (userId) => {
  const period = getCurrentPeriod();

  // ✅ Étape 1 : récupérer l'utilisateur
  const user = await User.findById(userId);
  if (!user) {
    throw new Error("Utilisateur introuvable");
  }

  const now = new Date();

  // ✅ Étape 2 : vérifier validité de la souscription
  const isValidSubscription =
    user.isSubscribed &&
    user.subscriptionStart &&
    user.subscriptionEnd &&
    now >= user.subscriptionStart &&
    now <= user.subscriptionEnd;

  // ❌ Souscription expirée → on annule et on bloque l’accès
  if (!isValidSubscription) {
    await User.findByIdAndUpdate(userId, {
      isSubscribed: false,
      subscriptionStart: null,
      subscriptionEnd: null,
    });

    throw new Error("Votre souscription est expirée. Veuillez souscrire à nouveau.");
  }

  // ✅ Étape 3 : vérifier ou créer le quota du mois
  let usage = await MonthlyUsage.findOne({ user: userId, period });

  if (!usage) {
    usage = await MonthlyUsage.create({ user: userId, period });
  }

  return usage;
};

module.exports = { getOrCreateMonthlyUsage };
