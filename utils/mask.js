// utils/mask.js
exports.maskCode = (s = "") => {
  if (!s) return "";
  // Garde les 4 derniers caractères
  const visible = s.slice(-4);
  const masked = s.slice(0, -4).replace(/./g, "*");
  return masked + visible; // ex: *****A1B2
};



// exports.maskCode = (s = "") => {
//   const str = String(s || "");
//   if (str.length <= 4) return "****";
//   return "*".repeat(str.length - 4) + str.slice(-4);
// };
