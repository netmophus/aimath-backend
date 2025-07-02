const express = require("express");
const router = express.Router();
const { helpIA } = require("../controllers/aiController");
//const { explainConcept, solveExercise} = require("../controllers/aiController");
const authMiddleware = require("../middlewares/authMiddleware");
const { authorizeRoles } = require("../middlewares/roleMiddleware");

const iaUsageLimiter = require("../middlewares/iaUsageLimiter");

// router.post("/explain", authMiddleware, authorizeRoles("eleve"), iaUsageLimiter, explainConcept);
// router.post("/solve", authMiddleware, authorizeRoles("eleve"), iaUsageLimiter, solveExercise);

router.post("/help", authMiddleware, authorizeRoles("eleve"), iaUsageLimiter, helpIA); // ✅ nouvelle route


module.exports = router;
