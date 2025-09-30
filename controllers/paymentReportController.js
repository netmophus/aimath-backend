// controllers/paymentReportController.js
const Payment = require("../models/PaymentHistory");
const User = require("../models/userModel");

// Détecte le mode de paiement à partir de la référence
function refToMethod(ref = "") {
  if (/^ACHAT/i.test(ref)) return "nita";
  if (/^FAH-/i.test(ref))  return "scratch";
  return "unknown";
}

// Plages temporelles pour le reporting
function getRange(period) {
  const now = new Date();
  switch (period) {
    case "7d":  return { start: new Date(now.getTime() - 7*24*3600*1000), end: now };
    case "30d": return { start: new Date(now.getTime() - 30*24*3600*1000), end: now };
    case "month": {
      const start = new Date(now.getFullYear(), now.getMonth(), 1);
      const end   = new Date(now.getFullYear(), now.getMonth() + 1, 1);
      return { start, end };
    }
    case "all":
    default:     return { start: new Date(0), end: now };
  }
}

// GET /payments/report?period=30d
async function getPaymentsReport(req, res, next) {
  try {
    const { period = "30d" } = req.query;
    const { start, end } = getRange(period);

    const rows = await Payment.aggregate([
      { $match: { paidAt: { $gte: start, $lt: end } } },
      {
        $addFields: {
          method: {
            $switch: {
              branches: [
                { case: { $regexMatch: { input: "$reference", regex: /^ACHAT/i } }, then: "nita" },
                { case: { $regexMatch: { input: "$reference", regex: /^FAH-/i } }, then: "scratch" },
              ],
              default: "unknown",
            }
          }
        }
      },
      { $group: { _id: "$method", count: { $sum: 1 }, amount: { $sum: "$amount" } } },
    ]);

    const by = Object.fromEntries(rows.map(r => [r._id, { count: r.count, amount: r.amount }]));
    const totals = rows.reduce((acc, r) => ({
      count: acc.count + r.count,
      amount: acc.amount + r.amount
    }), { count: 0, amount: 0 });

    res.json({
      period,
      totals,
      methods: {
        nita: by.nita || { count: 0, amount: 0 },
        scratch: by.scratch || { count: 0, amount: 0 },
        unknown: by.unknown || { count: 0, amount: 0 },
      }
    });
  } catch (err) {
    next(err);
  }
}

// GET /payments/recent?limit=10
async function getRecentPayments(req, res, next) {
  try {
    const limit = Math.max(1, Math.min(parseInt(req.query.limit || "20", 10), 100));
    const docs = await Payment.find({}).sort({ paidAt: -1 }).limit(limit).lean();

    res.json(docs.map(d => ({
      _id: d._id,
      user: d.user,
      phone: d.phone,
      amount: d.amount,
      reference: d.reference,
      method: refToMethod(d.reference),
      paidAt: d.paidAt,
    })));
  } catch (err) {
    next(err);
  }
}

/* =========================================================
   Utils
   --------------------------------------------------------- */
// Un utilisateur est considéré "sans abonnement" si:
// - isSubscribed === false
// - OU date d’expiration absente
// - OU subscriptionEnd est passée
function noSubMatch(now = new Date()) {
  return {
    $or: [
      { isSubscribed: false },
      { subscriptionEnd: { $exists: false } },
      { subscriptionEnd: { $lte: now } },
    ],
  };
}

/* =========================================================
   📊 getNoSubStats
   GET /payments/users/without-subscriptions/stats
   - total d’utilisateurs sans abonnement
   - répartition par rôle (eleve / teacher / partner / admin)
   - en option: inclure/exclure les comptes inactifs
   --------------------------------------------------------- */
async function getNoSubStats(req, res, next) {
  try {
    const now = new Date();
    const includeInactive = String(req.query.includeInactive || "true").toLowerCase() === "true";

    const match = noSubMatch(now);
    if (!includeInactive) match.isActive = true;

    const rows = await User.aggregate([
      { $match: match },
      {
        $group: {
          _id: "$role",
          count: { $sum: 1 },
        },
      },
    ]);

    const byRole = rows.reduce((acc, r) => {
      acc[r._id || "unknown"] = r.count;
      return acc;
    }, {});

    const total = rows.reduce((n, r) => n + r.count, 0);

    res.json({
      total,
      byRole, // ex: { eleve: 120, teacher: 8, partner: 3, admin: 1 }
    });
  } catch (err) {
    next(err);
  }
}

/* =========================================================
   📋 listNoSubUsers
   GET /payments/users/without-subscriptions
   Query params:
     - page (default 1)
     - limit (default 20)
     - q (recherche: phone / fullName)
     - includeInactive=true|false (default true)
     - sort (ex: "createdAt:desc", "lastLoginAt:desc")
   Retour:
     { items: [...], page, limit, total }
   --------------------------------------------------------- */
async function listNoSubUsers(req, res, next) {
  try {
    const now = new Date();
    const page = Math.max(1, parseInt(req.query.page || "1", 10));
    const limit = Math.max(1, Math.min(parseInt(req.query.limit || "20", 10), 100));
    const q = String(req.query.q || "").trim();
    const includeInactive = String(req.query.includeInactive || "true").toLowerCase() === "true";
    const sortParam = String(req.query.sort || "createdAt:desc");

    // tri
    let sort = { createdAt: -1 };
    if (sortParam) {
      const [field, dir] = sortParam.split(":");
      if (field) sort = { [field]: dir === "asc" ? 1 : -1 };
    }

    // match de base (sans abonnement)
    const match = noSubMatch(now);
    if (!includeInactive) match.isActive = true;

    // recherche textuelle basique (phone / fullName)
    if (q) {
      match.$and = (match.$and || []).concat([{
        $or: [
          { phone: { $regex: q, $options: "i" } },
          { fullName: { $regex: q, $options: "i" } },
        ],
      }]);
    }

    // pipeline: on récupère l’utilisateur + son dernier paiement (en optionnel)
    const pipeline = [
      { $match: match },
      {
        $lookup: {
          from: "payments", // nom de la collection (⚠️ dépend du nom réel en base)
          let: { userId: "$._id" },
          pipeline: [
            { $match: { $expr: { $eq: ["$user", "$$userId"] } } },
            { $sort: { paidAt: -1 } },
            { $limit: 1 },
          ],
          as: "lastPayment",
        },
      },
      { $unwind: { path: "$lastPayment", preserveNullAndEmptyArrays: true } },
      {
        $project: {
          fullName: 1,
          phone: 1,
          role: 1,
          city: 1,
          schoolName: 1,
          isActive: 1,
          isVerified: 1,
          isSubscribed: 1,
          subscriptionEnd: 1,
          paymentReference: 1,
          lastLoginAt: 1,
          createdAt: 1,

          lastPaymentAt: "$lastPayment.paidAt",
          lastPaymentRef: "$lastPayment.reference",
          lastPaymentAmount: "$lastPayment.amount",
        },
      },
      { $sort: sort },
      { $skip: (page - 1) * limit },
      { $limit: limit },
    ];

    const [items, totalRow] = await Promise.all([
      User.aggregate(pipeline),
      User.countDocuments(match),
    ]);

    res.json({
      items,
      page,
      limit,
      total: totalRow,
    });
  } catch (err) {
    next(err);
  }
}



module.exports = {
  getPaymentsReport,
  getRecentPayments,
   getNoSubStats,
  listNoSubUsers,
};
