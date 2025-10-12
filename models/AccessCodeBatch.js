const mongoose = require("mongoose");

const accessCodeBatchSchema = new mongoose.Schema({
  batchId: { type: String, required: true, unique: true },
  type: { type: String, enum: ["mensuel", "annuel"], required: true },
  generatedBy: { type: mongoose.Schema.Types.ObjectId, ref: "User" },
 price: { type: Number, required: true } ,// prix par carte du lot

codes: [
  {
    code: { type: String, required: true },
    status: {
      type: String,
      enum: ["generated", "assigned", "sold", "activated", "used"],
      default: "generated"
    },
    used: { type: Boolean, default: false },
    usedBy: { type: mongoose.Schema.Types.ObjectId, ref: "User", default: null },
    usedAt: { type: Date, default: null },
    createdAt: { type: Date, default: Date.now },
    price: { type: Number, required: false },  // ✅ Nouveau champ optionnel

     // ✅ nouveaux champs totalement optionnels (pour partenaires / traçabilité)
      partner: { type: mongoose.Schema.Types.ObjectId, ref: "User", default: null }, // user role="partner"
      assignedAt: { type: Date, default: null },
      soldAt: { type: Date, default: null },
      commissionCfa: { type: Number, default: 0 },   // commission figée à l’activation élève
       // ✅ N° de série optionnel (rempli automatiquement si manquant)
  serial: {
    type: String,
    default: function () {
      // fallback simple si non rempli au moment de la génération
      return this.code ? `S-${this.code.slice(-8).toUpperCase()}` : "";
    },
    trim: true,
  },

      activatedAt: { type: Date, default: null },    // date "activation commerciale" (status=activated)
  }
],



  totalCodes: { type: Number, required: true },
  createdAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model("AccessCodeBatch", accessCodeBatchSchema);
