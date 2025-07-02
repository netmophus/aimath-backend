const express = require("express");
const router = express.Router();
const fs = require("fs");
const path = require("path");

router.get("/:classe", (req, res) => {
  const { classe } = req.params; // ex: terminal-c
  const filePath = path.join(__dirname, "..", "data", "programmes", `${classe}.json`);

  try {
    const raw = fs.readFileSync(filePath, "utf8");
    const programme = JSON.parse(raw);
    res.json(programme);
  } catch (error) {
    console.error("❌ Erreur programme:", error.message);
    res.status(404).json({ message: "Programme introuvable" });
  }
});

module.exports = router;
