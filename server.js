// const express = require("express");
// const mongoose = require("mongoose");
// const dotenv = require("dotenv");
// const cors = require("cors");


// dotenv.config();

// // Logs des variables d'environnement Cloudinary
// console.log("✔️ CLOUDINARY_NAME:", process.env.CLOUDINARY_NAME);
// console.log("✔️ CLOUDINARY_API_KEY:", process.env.CLOUDINARY_API_KEY);
// console.log("✔️ CLOUDINARY_API_SECRET:", process.env.CLOUDINARY_API_SECRET);

// const app = express();
// const PORT = process.env.PORT || 5000;

// // 📦 Middlewares
// app.use(express.json());


// // 🔒 CORS

// const allowedOrigins = [
//   'https://fahimtafrontend-cf7031f2fb20.herokuapp.com',
//   'http://localhost:3000',
//   'http://127.0.0.1:3000',
//   'http://192.168.1.221:3000'
// ];

// // ✅ Middleware CORS dynamique et complet
// app.use(cors({
//   origin: function (origin, callback) {
//     // Autoriser les outils comme Postman ou appels sans origin
//     if (!origin || allowedOrigins.includes(origin)) {
//       callback(null, true);
//     } else {
//       callback(new Error('Not allowed by CORS'));
//     }
//   },
//   credentials: true,
//   methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
//   allowedHeaders: ['Content-Type', 'Authorization'],
//   optionsSuccessStatus: 200 // ✅ pour corriger les réponses 204 sur Heroku
// }));

// // ✅ Middleware manuel pour garantir les en-têtes
// app.use((req, res, next) => {
//   const origin = req.headers.origin;
//   if (allowedOrigins.includes(origin)) {
//     res.setHeader("Access-Control-Allow-Origin", origin);
//   }
//   res.setHeader("Access-Control-Allow-Credentials", "true");
//   res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
//   res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

//   if (req.method === "OPTIONS") {
//     return res.sendStatus(200);
//   }

//   next();
// });









// // 📡 Connexion MongoDB
// mongoose
//   .connect(process.env.MONGO_URI)
//   .then(() => console.log("✅ MongoDB connecté"))
//   .catch((err) => console.error("❌ Erreur MongoDB :", err));

// // 📁 Fichiers statiques
// app.use("/uploads", express.static("uploads"));

// // 🚦 Routes
// app.use("/api/auth", require("./routes/authRoutes"));
// app.use("/api/student", require("./routes/studentRoutes"));
// app.use("/api/admin", require("./routes/adminRoutes"));
// app.use("/api/admin/books", require("./routes/bookRoutes"));
// app.use("/api/gemini", require("./routes/geminiRoutes"));
// app.use("/api/ia", require("./routes/imageRoutes"));
// app.use("/api/ia", require("./routes/aiRoutes"));
// app.use("/api/ia/gratuit", require("./routes/gratuitRoutes"));
// app.use("/api/programmes", require("./routes/programmeRoutes"));
// app.use("/api/exams", require("./routes/examRoutes"));
// app.use("/api/videos", require("./routes/videoRoutes"));
// app.use("/api/payments", require("./routes/paymentRoutes"));


// // 🔍 Route test
// app.get("/", (req, res) => {
//   res.send("🎓 API Maths IA opérationnelle");
// });

// // 🚀 Lancement
// app.listen(PORT, () => {
//   console.log(`🚀 Serveur en cours sur http://127.0.0.1:${PORT}`);
// });






const express = require("express");
const mongoose = require("mongoose");
const dotenv = require("dotenv");
const cors = require("cors");
  const cron = require("node-cron");
const subscriptionReminderJob = require("./cron/subscriptionReminderJob");
dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;



// ✅ Origines autorisées
const allowedOrigins = [
  'https://fahimtafrontend-cf7031f2fb20.herokuapp.com',
//     'http://localhost:3000',
//    'http://127.0.0.1:3000',
//   'http://192.168.1.221:3000',
//  'http://192.168.80.55:3000'

 
];

// ✅ Middleware CORS dynamique
app.use(cors({
  origin: function (origin, callback) {
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Origin', 'X-Requested-With', 'Content-Type', 'Accept', 'Authorization'],
  optionsSuccessStatus: 200
}));

// ✅ Middleware manuel pour renforcer les en-têtes CORS
app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (allowedOrigins.includes(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept, Authorization");

if (req.method === "OPTIONS") {
  res.header("Access-Control-Allow-Origin", origin || "*");
  res.header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
  res.header("Access-Control-Allow-Headers", "Content-Type, Authorization");
  res.header("Access-Control-Allow-Credentials", "true");
  return res.status(200).end();
}


  next();
});

// ✅ Middleware JSON
//app.use(express.json());

app.use(express.json({ limit: '20mb' }));
app.use(express.urlencoded({ limit: '20mb', extended: true }));


// ✅ Connexion MongoDB
mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log("✅ MongoDB connecté"))
  .catch(err => console.error("❌ Erreur MongoDB :", err));




// 📆 Exécuter tous les jours à 8h du matin
cron.schedule("0 8 * * *", () => {
  console.log("📬 Lancement du rappel de fin d'abonnement...");
  subscriptionReminderJob();
});


// ✅ Routes API
app.use("/uploads", express.static("uploads"));
app.use("/api/auth", require("./routes/authRoutes"));
app.use("/api/students", require("./routes/studentRoutes"));
app.use("/api/admin", require("./routes/adminRoutes"));
app.use("/api/admin/books", require("./routes/bookRoutes"));
app.use("/api/users", require("./routes/userRoutes"));



// app.use("/api/books", require("./routes/publicBookRoutes")); // nouvelle route dédiée au téléchargement

// app.use("/api/gemini", require("./routes/geminiRoutes"));
app.use("/api/ia", require("./routes/imageRoutes"));
// app.use("/api/ia", require("./routes/aiRoutes"));
app.use("/api/ia/gratuit", require("./routes/gratuitRoutes"));
app.use("/api/programmes", require("./routes/programmeRoutes"));
app.use("/api/exams", require("./routes/examRoutes"));
app.use("/api/videos", require("./routes/videoRoutes"));
app.use("/api/payments", require("./routes/paymentRoutes"));
app.use("/api/usage", require("./routes/usageRoutes"));
app.use("/api/premium", require("./routes/premiumRoutes"));




app.use("/api/student", require("./routes/studentChatRoutes"));


app.use("/api/teacher", require("./routes/teacherChatRoutes"));



app.use("/api/teachers", require("./routes/teacherRoutes"));

// Utilisation des routes
app.use("/api/support-requests", require("./routes/supReqRoutes"));


app.use('/api/notifications', require('./routes/notificationsRoutes'));

app.use("/api/message-notifications", require("./routes/messageNotificationRoutes"));




// app.use('/api/profil', require("./routes/profilRoutes"));

// app.use("/api/chat", require("./routes/chatRoutes"));

// ✅ Route de test
app.get("/", (req, res) => {
  res.send("🎓 API Maths IA opérationnelle");
});

// ✅ Démarrage serveur
// app.listen(PORT, () => {
//   console.log(`🚀 Serveur en ligne sur http://127.0.0.1:${PORT}`);
// });

app.listen(PORT, '0.0.0.0', () => {
 console.log(`🚀 Serveur en ligne sur http://192.168.80.55:${PORT}`);
});
