const Tutorial = require("../models/tutorialModel");

// 📋 Récupérer tous les tutoriels actifs (pour le frontend public)
const getAllTutorials = async (req, res) => {
  try {
    const tutorials = await Tutorial.find({ isActive: true })
      .sort({ order: 1 })
      .select("-__v");

    res.status(200).json({
      success: true,
      count: tutorials.length,
      tutorials,
    });
  } catch (error) {
    console.error("Erreur récupération tutoriels:", error);
    res.status(500).json({
      success: false,
      message: "Erreur lors de la récupération des tutoriels",
    });
  }
};

// 📋 Récupérer tous les tutoriels (pour admin)
const getAllTutorialsAdmin = async (req, res) => {
  try {
    const tutorials = await Tutorial.find()
      .sort({ order: 1 })
      .select("-__v");

    res.status(200).json({
      success: true,
      count: tutorials.length,
      tutorials,
    });
  } catch (error) {
    console.error("Erreur récupération tutoriels admin:", error);
    res.status(500).json({
      success: false,
      message: "Erreur lors de la récupération des tutoriels",
    });
  }
};

// 🔍 Récupérer un tutoriel par ID
const getTutorialById = async (req, res) => {
  try {
    const tutorial = await Tutorial.findById(req.params.id);

    if (!tutorial) {
      return res.status(404).json({
        success: false,
        message: "Tutoriel non trouvé",
      });
    }

    res.status(200).json({
      success: true,
      tutorial,
    });
  } catch (error) {
    console.error("Erreur récupération tutoriel:", error);
    res.status(500).json({
      success: false,
      message: "Erreur lors de la récupération du tutoriel",
    });
  }
};

// ➕ Créer un nouveau tutoriel
const createTutorial = async (req, res) => {
  try {
    const { title, description, videoUrl, videoType, icon, color, order, isActive } = req.body;

    // Validation
    if (!title || !description || !videoUrl) {
      return res.status(400).json({
        success: false,
        message: "Titre, description et URL de la vidéo sont requis",
      });
    }

    const tutorial = await Tutorial.create({
      title,
      description,
      videoUrl,
      videoType: videoType || "direct",
      icon: icon || "HelpOutline",
      color: color || "#2196F3",
      order: order || 0,
      isActive: isActive !== undefined ? isActive : true,
    });

    res.status(201).json({
      success: true,
      message: "Tutoriel créé avec succès",
      tutorial,
    });
  } catch (error) {
    console.error("Erreur création tutoriel:", error);
    res.status(500).json({
      success: false,
      message: "Erreur lors de la création du tutoriel",
      error: error.message,
    });
  }
};

// ✏️ Mettre à jour un tutoriel
const updateTutorial = async (req, res) => {
  try {
    const { title, description, videoUrl, videoType, icon, color, order, isActive } = req.body;

    const tutorial = await Tutorial.findById(req.params.id);

    if (!tutorial) {
      return res.status(404).json({
        success: false,
        message: "Tutoriel non trouvé",
      });
    }

    // Mise à jour des champs
    if (title !== undefined) tutorial.title = title;
    if (description !== undefined) tutorial.description = description;
    if (videoUrl !== undefined) tutorial.videoUrl = videoUrl;
    if (videoType !== undefined) tutorial.videoType = videoType;
    if (icon !== undefined) tutorial.icon = icon;
    if (color !== undefined) tutorial.color = color;
    if (order !== undefined) tutorial.order = order;
    if (isActive !== undefined) tutorial.isActive = isActive;

    await tutorial.save();

    res.status(200).json({
      success: true,
      message: "Tutoriel mis à jour avec succès",
      tutorial,
    });
  } catch (error) {
    console.error("Erreur mise à jour tutoriel:", error);
    res.status(500).json({
      success: false,
      message: "Erreur lors de la mise à jour du tutoriel",
      error: error.message,
    });
  }
};

// 🗑️ Supprimer un tutoriel
const deleteTutorial = async (req, res) => {
  try {
    const tutorial = await Tutorial.findById(req.params.id);

    if (!tutorial) {
      return res.status(404).json({
        success: false,
        message: "Tutoriel non trouvé",
      });
    }

    await Tutorial.findByIdAndDelete(req.params.id);

    res.status(200).json({
      success: true,
      message: "Tutoriel supprimé avec succès",
    });
  } catch (error) {
    console.error("Erreur suppression tutoriel:", error);
    res.status(500).json({
      success: false,
      message: "Erreur lors de la suppression du tutoriel",
    });
  }
};

// 🔄 Toggle statut actif/inactif
const toggleTutorialStatus = async (req, res) => {
  try {
    const tutorial = await Tutorial.findById(req.params.id);

    if (!tutorial) {
      return res.status(404).json({
        success: false,
        message: "Tutoriel non trouvé",
      });
    }

    tutorial.isActive = !tutorial.isActive;
    await tutorial.save();

    res.status(200).json({
      success: true,
      message: `Tutoriel ${tutorial.isActive ? "activé" : "désactivé"}`,
      tutorial,
    });
  } catch (error) {
    console.error("Erreur toggle statut tutoriel:", error);
    res.status(500).json({
      success: false,
      message: "Erreur lors du changement de statut",
    });
  }
};

module.exports = {
  getAllTutorials,
  getAllTutorialsAdmin,
  getTutorialById,
  createTutorial,
  updateTutorial,
  deleteTutorial,
  toggleTutorialStatus,
};

