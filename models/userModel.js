
const mongoose = require("mongoose");
const bcrypt = require("bcryptjs");

const userSchema = new mongoose.Schema(
  {
    
    phone: {
  type: String,
  unique: true,
  sparse: true, // accepte plusieurs `null`
},

password: {
  type: String,
},


    email: {
  type: String,
  unique: true,
  sparse: true,
},
provider: {
  type: String,
  enum: ['local', 'google', 'facebook'],
  default: 'local',
},
providerId: {
  type: String,
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
      enum: ["eleve", "admin", "teacher"],
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

    profileCompleted: {
  type: Boolean,
  default: false,
},

photo: {
  type: String, // URL vers l'image (hébergée sur Cloudinary ou autre)
  default: "",  // ou une image par défaut
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
  if (
    !this.isModified("password") ||
    !this.password || 
    this.provider === 'google' || 
    this.provider === 'facebook'
  ) {
    return next();
  }

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
