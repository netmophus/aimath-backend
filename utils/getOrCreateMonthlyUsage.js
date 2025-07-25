
const MonthlyUsage = require("../models/MonthlyUsage");
const User = require("../models/userModel"); // ✅ à importer

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

  // ✅ Étape 2 : vérifier la validité de la souscription
  const now = new Date();
  const isValidSubscription =
    user.isSubscribed &&
    user.subscriptionStart &&
    user.subscriptionEnd &&
    now >= user.subscriptionStart &&
    now <= user.subscriptionEnd;

  if (!isValidSubscription) {
    throw new Error("Vous n'avez pas de souscription active.");
  }

  // ✅ Étape 3 : vérifier ou créer le quota du mois
  let usage = await MonthlyUsage.findOne({ user: userId, period });

  if (!usage) {
    usage = await MonthlyUsage.create({ user: userId, period });
  }

  return usage;
};

module.exports = { getOrCreateMonthlyUsage };
