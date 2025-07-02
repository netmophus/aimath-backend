const Video = require("../models/videoModel");
const cloudinary = require("cloudinary").v2;
const fs = require("fs");

const uploadToCloudinary = async (filePath, folder) => {
  const result = await cloudinary.uploader.upload(filePath, {
    folder,
    resource_type: "image",
  });
  fs.unlinkSync(filePath);
  return result.secure_url;
};

const createVideo = async (req, res) => {
  try {
    const { title, description, level, badge, videoUrl } = req.body;

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
    });

    res.status(201).json(video);
  } catch (err) {
    res.status(500).json({ message: "Erreur lors de la création de la vidéo." });
  }
};

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

    await video.save();

    res.json(video);
  } catch (err) {
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
};
