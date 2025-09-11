// models/distributorModel.js
const mongoose = require("mongoose");

const DistributorSchema = new mongoose.Schema(
  {
    // Identité
    name: { type: String, required: true, trim: true },       // Nom du point de vente
    contact: { type: String, trim: true },                    // Responsable (optionnel)

    // Coordonnées & zones
    region: { type: String, trim: true },                     // Ex: "Niamey", "Dosso", ...
    city:   { type: String, trim: true },                     // Ex: "Quartier, Commune..."

    address: { type: String, trim: true },                    // Rue / repère

    // Téléphones
    phone: {
      type: String,
      trim: true,
      match: [/^\+?\d[\d\s\-()]{6,}$/, "Numéro de téléphone invalide"],
    },
    whatsapp: {
      type: String,
      trim: true,
      match: [/^\+?\d[\d\s\-()]{6,}$/, "Numéro WhatsApp invalide"],
    },

    /**
     * Géolocalisation (GeoJSON)
     * ⛔️ IMPORTANT : pas de default "Point" — on n’enregistre `location`
     * que si on a un tableau [lng, lat] valide, sinon on laisse `undefined`.
     */
    location: {
      type: {
        type: String,
        enum: ["Point"],
      },
      coordinates: {
        type: [Number], // [lng, lat]
        validate: {
          validator: function (v) {
            if (!v || v.length === 0) return true; // autoriser vide
            if (v.length !== 2) return false;
            const [lng, lat] = v;
            return lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
          },
          message: "Coordonnées invalides (attendu: [lng, lat])",
        },
      },
    },

    // Disponibilité & métadonnées
    hasStock: { type: Boolean, default: true },
    openingHours: { type: String, trim: true },               // (optionnel)
    notes: { type: String, trim: true },                      // (optionnel)
    lastUpdated: { type: Date, default: Date.now },
    isActive: { type: Boolean, default: true },
  },
  { timestamps: true }
);

/* ------------ Index ------------ */
DistributorSchema.index({
  name: "text",
  city: "text",
  region: "text",
  address: "text",
});
DistributorSchema.index({ location: "2dsphere" });

/* ------------ Virtuals pratiques ------------ */
DistributorSchema.virtual("lat")
  .get(function () {
    return this.location?.coordinates?.length === 2
      ? this.location.coordinates[1]
      : undefined;
  })
  .set(function (val) {
    const lat = Number(val);
    if (Number.isFinite(lat)) {
      const lng = this.location?.coordinates?.[0] ?? 0;
      this.location = { type: "Point", coordinates: [lng, lat] };
    }
  });

DistributorSchema.virtual("lng")
  .get(function () {
    return this.location?.coordinates?.length === 2
      ? this.location.coordinates[0]
      : undefined;
  })
  .set(function (val) {
    const lng = Number(val);
    if (Number.isFinite(lng)) {
      const lat = this.location?.coordinates?.[1] ?? 0;
      this.location = { type: "Point", coordinates: [lng, lat] };
    }
  });

DistributorSchema.virtual("mapUrl").get(function () {
  const lat = this.lat;
  const lng = this.lng;
  if (typeof lat === "number" && typeof lng === "number") {
    return `https://www.google.com/maps?q=${lat},${lng}`;
  }
  if (this.address) {
    const q = encodeURIComponent(
      `${this.address} ${this.city || ""} ${this.region || ""}`.trim()
    );
    return `https://www.google.com/maps/search/?api=1&query=${q}`;
  }
  return null;
});

/* ------------ Hooks ------------ */
// 1) Ne pas laisser {type:"Point"} tout seul (sinon crash 2dsphere)
DistributorSchema.pre("validate", function (next) {
  const c = this.location?.coordinates;
  if (
    !Array.isArray(c) ||
    c.length !== 2 ||
    !Number.isFinite(c[0]) ||
    !Number.isFinite(c[1])
  ) {
    this.location = undefined;
  }
  next();
});

// 2) Mettre à jour lastUpdated si champs-clés changent
DistributorSchema.pre("save", function (next) {
  if (
    this.isModified("hasStock") ||
    this.isModified("address") ||
    this.isModified("location") ||
    this.isModified("openingHours")
  ) {
    this.lastUpdated = new Date();
  }
  next();
});

/* ------------ Projection JSON propre ------------ */
DistributorSchema.set("toJSON", {
  virtuals: true,
  transform: (_, ret) => {
    delete ret.__v;
    return ret;
  },
});

module.exports = mongoose.model("Distributor", DistributorSchema);
