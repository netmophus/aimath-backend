const express = require("express");
const router = express.Router();
const videoController = require("../controllers/videoController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const uploadVideo = require("../middlewares/uploadVideo"); // middleware pour image miniatures

const multerMiddleware = uploadVideo.single("thumbnail");

router.post(
  "/",
  authMiddleware,
  authorizeRoles("admin"),
  multerMiddleware,
  videoController.createVideo
);

router.put(
  "/:id",
  authMiddleware,
  authorizeRoles("admin"),
  multerMiddleware,
  videoController.updateVideo
);

router.delete(
  "/:id",
  authMiddleware,
  authorizeRoles("admin"),
  videoController.deleteVideo
);

router.get("/", videoController.getAllVideos);
router.get("/:id", videoController.getVideoById);

module.exports = router;
