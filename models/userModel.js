


// const mongoose = require("mongoose");
// const bcrypt = require("bcryptjs");

// const userSchema = new mongoose.Schema({
//   phone: {
//     type: String,
//     required: true,
//     unique: true,
//   },
//   password: {
//     type: String,
//     required: true,
//   },
//   otp: {
//     type: String,
//   },
//   isVerified: {
//     type: Boolean,
//     default: false,
//   },
//   isActive: {                  // ✅ AJOUTÉ
//     type: Boolean,
//     default: false,
//   },
//   role: {
//     type: String,
//     enum: ["eleve", "admin"],
//     default: "eleve",
//   },
//   classLevel: {
//     type: String,
//     enum: [
//       "6eme",
//       "5eme",
//       "4eme",
//       "3eme",
//       "seconde-a",
//       "seconde-c",
//       "premiere-a",
//       "premiere-c",
//       "premiere-d",
//       "terminale-a",
//       "terminale-c",
//       "terminale-d",
//     ],
//     required: function () {
//       return this.role === "eleve";
//     },
//   },
// }, {
//   timestamps: true,
// });

// // 🔐 Hash du mot de passe
// userSchema.pre("save", async function (next) {
//   if (!this.isModified("password")) return next();
//   const salt = await bcrypt.genSalt(10);
//   this.password = await bcrypt.hash(this.password, salt);
//   next();
// });

// // 🔐 Vérification du mot de passe
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
      required: true,
      unique: true,
    },
    password: {
      type: String,
      required: true,
    },
    fullName: {
      type: String,
      required: true,
    },
    schoolName: {
      type: String,
      required: true,
    },
    city: {
      type: String,
      required: true,
    },

    role: {
      type: String,
      enum: ["eleve", "admin"],
      default: "eleve",
    },

    isVerified: {
      type: Boolean,
      default: false,
    },
    isActive: {
      type: Boolean,
      default: true,
    },
    otp: String,

    isSubscribed: {
      type: Boolean,
      default: false,
    },
    subscriptionStart: Date,
    subscriptionEnd: Date,

paymentReference: { type: String },


    lastLoginAt: Date,
    loginCount: {
      type: Number,
      default: 0,
    },
  },
  {
    timestamps: true,
  }
);

// 🔐 Hash du mot de passe
userSchema.pre("save", async function (next) {
  if (!this.isModified("password")) return next();
  const salt = await bcrypt.genSalt(10);
  this.password = await bcrypt.hash(this.password, salt);
  next();
});

// 🔐 Vérification du mot de passe
userSchema.methods.matchPassword = async function (enteredPassword) {
  return await bcrypt.compare(enteredPassword, this.password);
};

const User = mongoose.model("User", userSchema);
module.exports = User;
