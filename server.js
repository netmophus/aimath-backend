const express = require("express");
const mongoose = require("mongoose");
const dotenv = require("dotenv");
const cors = require("cors");
const http = require("http");
const { Server } = require("socket.io");
const cron = require("node-cron");
const subscriptionReminderJob = require("./cron/subscriptionReminderJob");
dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

// ✅ Créer serveur HTTP pour Socket.io
const server = http.createServer(app);

const distributorRoutes = require("./routes/distributorRoutes");


// ✅ Origines autorisées
// const allowedOrigins = [
//   //  'https://fahimtafrontend-cf7031f2fb20.herokuapp.com',
//   //   'http://localhost:3000',
//   //  'http://127.0.0.1:3000',
//   'http://192.168.1.221:3000',

 
// ];


const allowedOrigins = [

 'https://fahimtafrontend-cf7031f2fb20.herokuapp.com',
  'https://myfahimta.com',
    'https://www.myfahimta.com',
//  'http://localhost:3000',
//  'http://127.0.0.1:3000',
//   'http://192.168.80.241:3000',
//   'http://192.168.1.221:3000',
//   'http://192.168.80.198:3000',
//   'http:/192.168.0.100:3000',
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

// ✅ Initialiser Socket.io avec CORS
const io = new Server(server, {
  cors: {
    origin: allowedOrigins,
    methods: ["GET", "POST"],
    credentials: true,
  },
});

// ✅ Gestion des connexions Socket.io
require("./socket/socketHandler")(io);

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

// API routes
app.use("/api/distributors", distributorRoutes);


app.use("/api/student", require("./routes/studentChatRoutes"));


app.use("/api/teacher", require("./routes/teacherChatRoutes"));



app.use("/api/teachers", require("./routes/teacherRoutes"));

// Utilisation des routes
app.use("/api/support-requests", require("./routes/supReqRoutes"));


app.use('/api/notifications', require('./routes/notificationsRoutes'));

app.use("/api/message-notifications", require("./routes/messageNotificationRoutes"));

// ✅ Routes demandes de contenu (élèves premium → admin)
app.use("/api/content-requests", require("./routes/contentRequestRoutes"));

// ✅ Route Tutorials (Vidéos tutorielles)
app.use("/api/tutorials", require("./routes/tutorialRoutes"));

// ✅ Route Bibliothèque (Livres par matière)
app.use("/api/library", require("./routes/libraryRoutes"));

// ✅ Route Admin Bibliothèque (Gestion des livres)
app.use("/api/admin/library", require("./routes/adminLibraryRoutes"));

const paymentReportRoutes = require("./routes/paymentReportRoutes");
app.use("/api/payments", paymentReportRoutes);  


// app.use('/api/profil', require("./routes/profilRoutes"));

// app.use("/api/chat", require("./routes/chatRoutes"));

// ✅ Route de test
app.get("/", (req, res) => {
  res.send("🎓 API Maths IA opérationnelle");
});

// ✅ Démarrage serveur avec Socket.io
server.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Serveur en ligne sur http://192.168.80.36:${PORT}`);
  console.log(`🔌 Socket.io activé pour temps réel`);
});
