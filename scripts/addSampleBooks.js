const mongoose = require("mongoose");
const LibraryBook = require("../models/Book");
require("dotenv").config();

// Connexion à MongoDB
mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log("✅ MongoDB connecté"))
  .catch(err => console.error("❌ Erreur MongoDB :", err));

// Données d'exemple pour les livres
const sampleBooks = [
  // MÉDECINE
  {
    title: "Anatomie et Physiologie Humaine",
    author: "Dr. Marie Dubois",
    description: "Manuel complet d'anatomie et physiologie pour étudiants en médecine",
    subject: "medecine",
    level: "universite",
    pages: 450,
    year: 2023,
    summary: [
      "Chapitre 1: Introduction à l'anatomie",
      "Chapitre 2: Système squelettique",
      "Chapitre 3: Système musculaire",
      "Chapitre 4: Système cardiovasculaire",
      "Chapitre 5: Système respiratoire",
      "Chapitre 6: Système digestif",
      "Chapitre 7: Système nerveux",
      "Chapitre 8: Système endocrinien"
    ],
    tags: ["anatomie", "physiologie", "médecine"],
    language: "fr",
    isAvailable: true,
    downloads: 0,
    views: 0,
    filePath: "sample-medecine-1.pdf", // Vous devrez ajouter le vrai fichier
    fileSize: 1024000, // 1MB
    addedBy: new mongoose.Types.ObjectId(), // ID d'un admin existant
  },
  {
    title: "Pathologie Générale",
    author: "Prof. Jean Martin",
    description: "Étude des maladies et de leurs mécanismes",
    subject: "medecine",
    level: "universite",
    pages: 380,
    year: 2022,
    summary: [
      "Chapitre 1: Introduction à la pathologie",
      "Chapitre 2: Inflammation et réparation",
      "Chapitre 3: Troubles de la croissance cellulaire",
      "Chapitre 4: Pathologie cardiovasculaire",
      "Chapitre 5: Pathologie respiratoire",
      "Chapitre 6: Pathologie digestive"
    ],
    tags: ["pathologie", "maladies", "médecine"],
    language: "fr",
    isAvailable: true,
    downloads: 0,
    views: 0,
    filePath: "sample-medecine-2.pdf",
    fileSize: 950000,
    addedBy: new mongoose.Types.ObjectId(),
  },

  // BIOLOGIE
  {
    title: "Biologie Cellulaire et Moléculaire",
    author: "Dr. Sophie Laurent",
    description: "Fondamentaux de la biologie cellulaire moderne",
    subject: "biologie",
    level: "universite",
    pages: 520,
    year: 2023,
    summary: [
      "Chapitre 1: Structure de la cellule",
      "Chapitre 2: Membrane cellulaire",
      "Chapitre 3: Noyau et ADN",
      "Chapitre 4: Métabolisme cellulaire",
      "Chapitre 5: Division cellulaire",
      "Chapitre 6: Communication cellulaire"
    ],
    tags: ["biologie", "cellule", "moléculaire"],
    language: "fr",
    isAvailable: true,
    downloads: 0,
    views: 0,
    filePath: "sample-biologie-1.pdf",
    fileSize: 1200000,
    addedBy: new mongoose.Types.ObjectId(),
  },

  // MATHÉMATIQUES
  {
    title: "Analyse Mathématique Avancée",
    author: "Prof. Ahmed Hassan",
    description: "Cours complet d'analyse pour étudiants universitaires",
    subject: "mathematiques",
    level: "universite",
    pages: 600,
    year: 2023,
    summary: [
      "Chapitre 1: Limites et continuité",
      "Chapitre 2: Dérivées et applications",
      "Chapitre 3: Intégrales",
      "Chapitre 4: Suites et séries",
      "Chapitre 5: Fonctions de plusieurs variables",
      "Chapitre 6: Équations différentielles"
    ],
    tags: ["mathématiques", "analyse", "calcul"],
    language: "fr",
    isAvailable: true,
    downloads: 0,
    views: 0,
    filePath: "sample-maths-1.pdf",
    fileSize: 1500000,
    addedBy: new mongoose.Types.ObjectId(),
  },

  // INFORMATIQUE
  {
    title: "Algorithmes et Structures de Données",
    author: "Dr. Fatima Al-Zahra",
    description: "Guide complet des algorithmes fondamentaux",
    subject: "informatique",
    level: "universite",
    pages: 480,
    year: 2023,
    summary: [
      "Chapitre 1: Complexité algorithmique",
      "Chapitre 2: Structures de données de base",
      "Chapitre 3: Algorithmes de tri",
      "Chapitre 4: Algorithmes de recherche",
      "Chapitre 5: Graphes et arbres",
      "Chapitre 6: Programmation dynamique"
    ],
    tags: ["informatique", "algorithmes", "programmation"],
    language: "fr",
    isAvailable: true,
    downloads: 0,
    views: 0,
    filePath: "sample-info-1.pdf",
    fileSize: 1100000,
    addedBy: new mongoose.Types.ObjectId(),
  },

  // ÉCONOMIE
  {
    title: "Microéconomie et Macroéconomie",
    author: "Prof. Ibrahim Diallo",
    description: "Principes fondamentaux de l'économie moderne",
    subject: "economie",
    level: "universite",
    pages: 420,
    year: 2023,
    summary: [
      "Chapitre 1: Introduction à l'économie",
      "Chapitre 2: Offre et demande",
      "Chapitre 3: Élasticité",
      "Chapitre 4: Production et coûts",
      "Chapitre 5: Marchés et concurrence",
      "Chapitre 6: Macroéconomie de base"
    ],
    tags: ["économie", "microéconomie", "macroéconomie"],
    language: "fr",
    isAvailable: true,
    downloads: 0,
    views: 0,
    filePath: "sample-economie-1.pdf",
    fileSize: 980000,
    addedBy: new mongoose.Types.ObjectId(),
  }
];

// Fonction pour ajouter les livres
async function addSampleBooks() {
  try {
    console.log("📚 Ajout des livres d'exemple...");
    
    // Supprimer les livres existants (optionnel)
    // await LibraryBook.deleteMany({});
    
    // Ajouter les nouveaux livres
    const addedBooks = await LibraryBook.insertMany(sampleBooks);
    
    console.log(`✅ ${addedBooks.length} livres ajoutés avec succès !`);
    
    // Afficher un résumé
    const booksBySubject = {};
    addedBooks.forEach(book => {
      if (!booksBySubject[book.subject]) {
        booksBySubject[book.subject] = 0;
      }
      booksBySubject[book.subject]++;
    });
    
    console.log("\n📊 Répartition par matière :");
    Object.entries(booksBySubject).forEach(([subject, count]) => {
      console.log(`  - ${subject}: ${count} livres`);
    });
    
  } catch (error) {
    console.error("❌ Erreur lors de l'ajout des livres :", error);
  } finally {
    mongoose.connection.close();
    console.log("🔌 Connexion fermée");
  }
}

// Exécuter le script
addSampleBooks();
