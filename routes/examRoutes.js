const express = require("express");
const router = express.Router();
const examController = require("../controllers/examController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");
const uploadExam = require("../middlewares/uploadExam");

const multerMiddleware = uploadExam.fields([
  { name: "subject", maxCount: 1 },
  { name: "correction", maxCount: 1 },
  { name: "cover", maxCount: 1 }
]);

router.post(
  "/",
  authMiddleware,
  authorizeRoles("admin"),
  multerMiddleware,
  examController.createExam
);

router.get("/", examController.getAllExams);

router.put(
  "/:id",
  authMiddleware,
  authorizeRoles("admin"),
  multerMiddleware,
  examController.updateExam
);

router.delete(
  "/:id",
  authMiddleware,
  authorizeRoles("admin"),
  examController.deleteExam
);

module.exports = router;
