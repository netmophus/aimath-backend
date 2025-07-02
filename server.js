const express = require("express");
const mongoose = require("mongoose");
const dotenv = require("dotenv");
const cors = require("cors");


dotenv.config();

// Logs des variables d'environnement Cloudinary
console.log("✔️ CLOUDINARY_NAME:", process.env.CLOUDINARY_NAME);
console.log("✔️ CLOUDINARY_API_KEY:", process.env.CLOUDINARY_API_KEY);
console.log("✔️ CLOUDINARY_API_SECRET:", process.env.CLOUDINARY_API_SECRET);

const app = express();
const PORT = process.env.PORT || 5000;

// 📦 Middlewares
app.use(express.json());


// 🔒 CORS




// 📌 1️⃣ Configuration des origines autorisées
const allowedOrigins = [
  'https://fahimtafrontend-cf7031f2fb20.herokuapp.com',
  'http://localhost:3000',
  'http://127.0.0.1:3000',
  'http://192.168.1.221:3000'
];

// 📌 2️⃣ Middleware CORS (via le module)
app.use(cors({
  origin: allowedOrigins,
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true
}));

// 📌 3️⃣ Middleware manuel pour garantir les en-têtes CORS
app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (allowedOrigins.includes(origin)) {
    res.header('Access-Control-Allow-Origin', origin);
  }
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.header('Access-Control-Allow-Credentials', 'true');

  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }

  next();
});









// 📡 Connexion MongoDB
mongoose
  .connect(process.env.MONGO_URI)
  .then(() => console.log("✅ MongoDB connecté"))
  .catch((err) => console.error("❌ Erreur MongoDB :", err));

// 📁 Fichiers statiques
app.use("/uploads", express.static("uploads"));

// 🚦 Routes
app.use("/api/auth", require("./routes/authRoutes"));
app.use("/api/student", require("./routes/studentRoutes"));
app.use("/api/admin", require("./routes/adminRoutes"));
app.use("/api/admin/books", require("./routes/bookRoutes"));
app.use("/api/gemini", require("./routes/geminiRoutes"));
app.use("/api/ia", require("./routes/imageRoutes"));
app.use("/api/ia", require("./routes/aiRoutes"));
app.use("/api/ia/gratuit", require("./routes/gratuitRoutes"));
app.use("/api/programmes", require("./routes/programmeRoutes"));
app.use("/api/exams", require("./routes/examRoutes"));
app.use("/api/videos", require("./routes/videoRoutes"));
app.use("/api/payments", require("./routes/paymentRoutes"));


// 🔍 Route test
app.get("/", (req, res) => {
  res.send("🎓 API Maths IA opérationnelle");
});

// 🚀 Lancement
app.listen(PORT, () => {
  console.log(`🚀 Serveur en cours sur http://127.0.0.1:${PORT}`);
});
