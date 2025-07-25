const User = require("../models/userModel");
const sendSMS = require("../utils/sendSMS"); // Utilise ta fonction SMS

const subscriptionReminderJob = async () => {
  const now = new Date();
  const oneDayLater = new Date(now.getTime() + 24 * 60 * 60 * 1000);

  try {
    const usersToRemind = await User.find({
      isSubscribed: true,
      subscriptionEnd: {
        $gte: new Date(oneDayLater.setHours(0, 0, 0, 0)),
        $lt: new Date(oneDayLater.setHours(23, 59, 59, 999)),
      }
    });

    for (const user of usersToRemind) {
      if (user.phone) {
        await sendSMS(
          user.phone,
          `📢 Bonjour ${user.fullName}, votre abonnement Fahimta expire demain. Pensez à renouveler votre carte d’accès.`
        );
        console.log(`✅ Rappel envoyé à ${user.fullName}`);
      }
    }
  } catch (error) {
    console.error("❌ Erreur lors de l'envoi des rappels :", error);
  }
};

module.exports = subscriptionReminderJob;
