const Video = require("../models/videoModel");
const cloudinary = require("cloudinary").v2;
const fs = require("fs");
const { getOrCreateMonthlyUsage } = require("../utils/getOrCreateMonthlyUsage");



const watchVideo = async (req, res) => {
  try {
    const video = await Video.findById(req.params.id);
    if (!video) {
      return res.status(404).json({ message: "❌ Vidéo introuvable." });
    }

    if (!req.user.isSubscribed) {
      return res.status(403).json({ message: "⛔ Réservé aux abonnés." });
    }

    return res.status(200).json({ videoUrl: video.videoUrl }); // ✅ renvoie le lien
  } catch (err) {
    console.error("Erreur vidéo :", err.message);
    res.status(500).json({ message: "Erreur lors de l'accès à la vidéo." });
  }
};




const uploadToCloudinary = async (filePath, folder) => {
  const result = await cloudinary.uploader.upload(filePath, {
    folder,
    resource_type: "image",
  });
  fs.unlinkSync(filePath);
  return result.secure_url;
};

// const createVideo = async (req, res) => {
//   try {
//     const { title, description, level, badge, videoUrl } = req.body;

//     let thumbnail = "";
//     if (req.file?.path) {
//       thumbnail = await uploadToCloudinary(req.file.path, "videos/thumbnails");
//     }

//     const video = await Video.create({
//       title,
//       description,
//       level,
//       badge,
//       videoUrl,
//       thumbnail,
//     });

//     res.status(201).json(video);
//   } catch (err) {
//     res.status(500).json({ message: "Erreur lors de la création de la vidéo." });
//   }
// };


const createVideo = async (req, res) => {
  try {
    const { title, description, level, badge, videoUrl } = req.body;

    let videosSupplementaires = [];
    if (req.body.videosSupplementaires) {
      try {
        videosSupplementaires = JSON.parse(req.body.videosSupplementaires);
      } catch (parseErr) {
        return res.status(400).json({ message: "Format des vidéos supplémentaires invalide." });
      }
    }

    let thumbnail = "";
    if (req.file?.path) {
      thumbnail = await uploadToCloudinary(req.file.path, "videos/thumbnails");
    }

    const video = await Video.create({
      title,
      description,
      level,
      badge,
      videoUrl,
      thumbnail,
      videosSupplementaires,
    });

    res.status(201).json(video);
  } catch (err) {
    console.error("Erreur création vidéo:", err);
    res.status(500).json({ message: "Erreur lors de la création de la vidéo." });
  }
};




// const updateVideo = async (req, res) => {
//   try {
//     const video = await Video.findById(req.params.id);
//     if (!video) return res.status(404).json({ message: "Vidéo non trouvée." });

//     const { title, description, level, badge, videoUrl } = req.body;

//     if (req.file?.path) {
//       const newThumbnail = await uploadToCloudinary(req.file.path, "videos/thumbnails");
//       video.thumbnail = newThumbnail;
//     }

//     video.title = title || video.title;
//     video.description = description || video.description;
//     video.level = level || video.level;
//     video.badge = badge || video.badge;
//     video.videoUrl = videoUrl || video.videoUrl;

//     await video.save();

//     res.json(video);
//   } catch (err) {
//     res.status(500).json({ message: "Erreur lors de la mise à jour." });
//   }
// };


const updateVideo = async (req, res) => {
  try {
    const video = await Video.findById(req.params.id);
    if (!video) return res.status(404).json({ message: "Vidéo non trouvée." });

    const { title, description, level, badge, videoUrl } = req.body;

    if (req.file?.path) {
      const newThumbnail = await uploadToCloudinary(req.file.path, "videos/thumbnails");
      video.thumbnail = newThumbnail;
    }

    video.title = title || video.title;
    video.description = description || video.description;
    video.level = level || video.level;
    video.badge = badge || video.badge;
    video.videoUrl = videoUrl || video.videoUrl;

    // ✅ Ajout du parsing des vidéos supplémentaires
    if (req.body.videosSupplementaires) {
      try {
        const parsed = JSON.parse(req.body.videosSupplementaires);
        if (Array.isArray(parsed)) {
          video.videosSupplementaires = parsed;
        }
      } catch (parseErr) {
        return res.status(400).json({ message: "Format des vidéos supplémentaires invalide." });
      }
    }

    await video.save();

    res.json(video);
  } catch (err) {
    console.error("Erreur mise à jour vidéo:", err);
    res.status(500).json({ message: "Erreur lors de la mise à jour." });
  }
};






const deleteVideo = async (req, res) => {
  try {
    const video = await Video.findByIdAndDelete(req.params.id);
    if (!video) return res.status(404).json({ message: "Vidéo non trouvée." });

    res.json({ message: "Vidéo supprimée avec succès." });
  } catch (err) {
    res.status(500).json({ message: "Erreur lors de la suppression." });
  }
};

const getAllVideos = async (req, res) => {
  try {
    const videos = await Video.find().sort({ createdAt: -1 });
    res.json(videos);
  } catch (err) {
    res.status(500).json({ message: "Erreur lors de la récupération des vidéos." });
  }
};

const getVideoById = async (req, res) => {
  try {
    const video = await Video.findById(req.params.id);
    if (!video) return res.status(404).json({ message: "Vidéo non trouvée." });

    res.json(video);
  } catch (err) {
    res.status(500).json({ message: "Erreur lors de la récupération." });
  }
};

module.exports = {
  createVideo,
  updateVideo,
  deleteVideo,
  getAllVideos,
  getVideoById,
  // watchVideoWithLimit,
  watchVideo,

};
