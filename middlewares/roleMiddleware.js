// const authorizeRoles = (...allowedRoles) => {
//     return (req, res, next) => {
//       if (!req.user || !allowedRoles.includes(req.user.role)) {
//         return res.status(403).json({ message: "Accès non autorisé." });
//       }
//       next();
//     };
//   };
  
//   module.exports = { authorizeRoles };
  



const authorizeRoles = (...allowedRoles) => {
  return (req, res, next) => {
    console.log("🛂 Rôle de l'utilisateur connecté :", req.user?.role);
    console.log("✅ Rôles autorisés :", allowedRoles);

    if (!req.user || !allowedRoles.includes(req.user.role)) {
      console.log("❌ Accès refusé");
      return res.status(403).json({ message: "Accès non autorisé." });
    }

    console.log("✅ Accès autorisé");
    next();
  };
};

module.exports = { authorizeRoles };
