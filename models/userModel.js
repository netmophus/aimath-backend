



// const mongoose = require("mongoose");
// const bcrypt = require("bcryptjs");

// const userSchema = new mongoose.Schema(
//   {
//     phone: {
//       type: String,
//       unique: true,
//       sparse: true, // accepte plusieurs `null`
//     },

//     password: {
//       type: String,
//     },

//     email: {
//       type: String,
//       unique: true,
//       sparse: true,
//     },

//     provider: {
//       type: String,
//       enum: ["local", "google", "facebook"],
//       default: "local",
//     },
//     providerId: {
//       type: String,
//     },

//     fullName: {
//       type: String,
//       required: true,
//     },
//     schoolName: {
//       type: String,
//       required: true,
//     },
//     city: {
//       type: String,
//       required: true,
//     },

//     role: {
//       type: String,
//       enum: ["eleve", "admin", "teacher"],
//       default: "eleve",
//     },

//     isVerified: {
//       type: Boolean,
//       default: false,
//     },
//     isActive: {
//       type: Boolean,
//       default: true,
//     },

//     profileCompleted: {
//       type: Boolean,
//       default: false,
//     },

//     photo: {
//       type: String, // URL vers l'image (Cloudinary ou autre)
//       default: "",
//     },

//     otp: String,

//     isSubscribed: {
//       type: Boolean,
//       default: false,
//     },
//     subscriptionStart: Date,
//     subscriptionEnd: Date,

//     paymentReference: { type: String },

//     lastLoginAt: Date,
//     loginCount: {
//       type: Number,
//       default: 0,
//     },
//   },
//   {
//     timestamps: true,
//   }
// );

// /* --------- Virtual pour la confirmation de mot de passe --------- */
// userSchema.virtual("passwordConfirm")
//   .get(function () { return this._passwordConfirm; })
//   .set(function (v) { this._passwordConfirm = v; });

// /* --------- Vérification simple avant validation --------- */
// userSchema.pre("validate", function (next) {
//   // SSO : pas de mot de passe requis
//   if (this.provider && this.provider !== "local") return next();

//   // Ne vérifier que si le mot de passe est modifié/créé
//   if (!this.isModified("password")) return next();

//   if (!this.password) {
//     this.invalidate("password", "Le mot de passe est requis.");
//   }
//   if (this.password !== this._passwordConfirm) {
//     this.invalidate("passwordConfirm", "La confirmation du mot de passe ne correspond pas.");
//   }
//   next();
// });

// /* --------- Hash du mot de passe avant sauvegarde --------- */
// userSchema.pre("save", async function (next) {
//   if (
//     !this.isModified("password") ||
//     !this.password ||
//     this.provider === "google" ||
//     this.provider === "facebook"
//   ) {
//     return next();
//   }

//   const salt = await bcrypt.genSalt(10);
//   this.password = await bcrypt.hash(this.password, salt);
//   next();
// });

// /* --------- Méthode de comparaison --------- */
// userSchema.methods.matchPassword = async function (enteredPassword) {
//   return await bcrypt.compare(enteredPassword, this.password);
// };

// const User = mongoose.model("User", userSchema);
// module.exports = User;




const mongoose = require("mongoose");
const bcrypt = require("bcryptjs");

const userSchema = new mongoose.Schema(
  {
    phone: {
      type: String,
      unique: true,   // index unique sur le téléphone (on conserve)
      sparse: true,   // autorise plusieurs null
    },

    password: { type: String },

    provider: {
      type: String,
      enum: ["local", "google", "facebook"],
      default: "local",
    },
    providerId: { type: String },

    fullName: { type: String, required: true },
    schoolName: { type: String, required: true },
    city: { type: String, required: true },

    role: {
      type: String,
      enum: ["eleve", "admin", "teacher"],
      default: "eleve",
    },

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
  },
  { timestamps: true }
);

/* --------- Virtual: confirmation de mot de passe --------- */
userSchema.virtual("passwordConfirm")
  .get(function () { return this._passwordConfirm; })
  .set(function (v) { this._passwordConfirm = v; });

/* --------- Validation simple --------- */
userSchema.pre("validate", function (next) {
  // Pas d’exigence de mot de passe pour SSO
  if (this.provider && this.provider !== "local") return next();

  if (!this.isModified("password")) return next();

  if (!this.password) {
    this.invalidate("password", "Le mot de passe est requis.");
  }
  if (this.password !== this._passwordConfirm) {
    this.invalidate("passwordConfirm", "La confirmation du mot de passe ne correspond pas.");
  }
  next();
});

/* --------- Hash du mot de passe --------- */
userSchema.pre("save", async function (next) {
  if (
    !this.isModified("password") ||
    !this.password ||
    this.provider === "google" ||
    this.provider === "facebook"
  ) {
    return next();
  }
  const salt = await bcrypt.genSalt(10);
  this.password = await bcrypt.hash(this.password, salt);
  next();
});

/* --------- Comparaison --------- */
userSchema.methods.matchPassword = async function (enteredPassword) {
  return bcrypt.compare(enteredPassword, this.password);
};

module.exports = mongoose.model("User", userSchema);
