const { getOrCreateMonthlyUsage } = require("../utils/getOrCreateMonthlyUsage");

exports.getMyMonthlyUsage = async (req, res) => {
  try {
    const usage = await getOrCreateMonthlyUsage(req.user._id);

    res.json({
      booksRemaining: Math.max(5 - usage.booksDownloaded, 0),
      videosRemaining: Math.max(5 - usage.videosWatched, 0),
      examsRemaining: Math.max(3 - usage.examsDownloaded, 0),
       correctionsRemaining: 3 - usage.examsCorrectionsDownloaded,
      iaTextRemaining: Math.max(20 - usage.iaTextQuestions, 0),      // nouveau champ
      iaImageRemaining: Math.max(10 - usage.iaImageQuestions, 0),    // nouveau champ
      iaVisionRemaining: Math.max(10 - usage.iaGptVisionQuestions, 0), // 👈 nouveau champ
    });
  } catch (err) {
    console.error("❌ Erreur récupération usage :", err.message);
    res.status(500).json({ message: "Erreur serveur." });
  }
};

