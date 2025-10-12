

// models/userModel.js
const mongoose = require("mongoose");
const bcrypt = require("bcryptjs");

const userSchema = new mongoose.Schema(
  {
    phone: { type: String, unique: true, sparse: true },
    password: { type: String },

    provider: { type: String, enum: ["local", "google", "facebook"], default: "local" },
    providerId: { type: String },

    fullName: { type: String, required: true },

    // ⚠️ ÉTAIENT "required: true" → à rendre optionnels pour supporter le rôle partner
    schoolName: { type: String, default: "" },
    city: { type: String, default: "" },

    role: {
      type: String,
      enum: ["eleve", "admin", "teacher", "partner"],
      default: "eleve",
    },

    // ✅ Champs dédiés partenaires
    companyName: { type: String, default: "" },
    region: { type: String, default: "" },
    commissionDefaultCfa: { type: Number, default: 0 },

    isVerified: { type: Boolean, default: false },
    isActive: { type: Boolean, default: true },
    profileCompleted: { type: Boolean, default: false },
    photo: { type: String, default: "" },
    otp: String,

    isSubscribed: { type: Boolean, default: false },
    subscriptionStart: Date,
    subscriptionEnd: Date,
    paymentReference: { type: String },

    lastLoginAt: Date,
    loginCount: { type: Number, default: 0 },

     // 👇 NEW: optionnel, pas de default → ne casse rien
  firstLoginAt: { type: Date, default: null },
  
  // Cartes achetées par l'utilisateur
  cards: [{
    code: { type: String, required: true },
    price: { type: Number, required: true },
    status: { type: String, enum: ["en_attente", "utilisé", "annulé"], default: "en_attente" },
    serialNumber: { type: String },
    batchId: { type: String },
    purchaseDate: { type: Date, default: Date.now },
    partnerName: { type: String },
    partnerPhone: { type: String },
    saleId: { type: String },
    createdAt: { type: Date, default: Date.now }
  }],
  },
  { timestamps: true }
);

// (vos hooks/virtuals restent inchangés)
userSchema.virtual("passwordConfirm")
  .get(function () { return this._passwordConfirm; })
  .set(function (v) { this._passwordConfirm = v; });

userSchema.pre("validate", function (next) {
  if (this.provider && this.provider !== "local") return next();
  if (!this.isModified("password")) return next();
  if (!this.password) this.invalidate("password", "Le mot de passe est requis.");
  if (this.password !== this._passwordConfirm) {
    this.invalidate("passwordConfirm", "La confirmation du mot de passe ne correspond pas.");
  }
  next();
});

userSchema.pre("save", async function (next) {
  if (!this.isModified("password") || !this.password || this.provider !== "local") return next();
  const salt = await bcrypt.genSalt(10);
  this.password = await bcrypt.hash(this.password, salt);
  next();
});

userSchema.methods.matchPassword = async function (enteredPassword) {
  return bcrypt.compare(enteredPassword, this.password);
};

module.exports = mongoose.model("User", userSchema);
