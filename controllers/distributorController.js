// controllers/distributorController.js
const Distributor = require("../models/distributorModel");

/* Utils */
const toNum = (v) => {
  if (v === null || v === undefined || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
};

/* CREATE (admin) */
exports.createDistributor = async (req, res) => {
  try {
    const {
      name,
      contact,
      region,
      city,
      address,
      phone,
      whatsapp,
      latitude,
      longitude,
      hasStock,
      openingHours,
      notes,
      isActive,
    } = req.body;

    const doc = new Distributor({
      name,
      contact,
      region,
      city,
      address,
      phone,
      whatsapp,
      hasStock: typeof hasStock === "boolean" ? hasStock : true,
      openingHours,
      notes,
      isActive: isActive !== false,
    });

    const lat = toNum(latitude);
    const lng = toNum(longitude);
    if (lat !== undefined && lng !== undefined) {
      doc.location = { type: "Point", coordinates: [lng, lat] };
    }

    await doc.save();
    return res.status(201).json(doc);
  } catch (err) {
    console.error("createDistributor error:", err);
    return res.status(500).json({ message: err.message || "Erreur serveur." });
  }
};

/* LIST (public) — recherche + pagination */
exports.listDistributors = async (req, res) => {
  try {
    let { page = 1, pageSize = 10, search = "", region, city, active } = req.query;
    page = Math.max(parseInt(page, 10) || 1, 1);
    pageSize = Math.min(Math.max(parseInt(pageSize, 10) || 10, 1), 100);

    const filter = {};
    if (active === "true") filter.isActive = true;
    if (active === "false") filter.isActive = false;
    if (region) filter.region = region;
    if (city) filter.city = city;

    // texte plein via index $text si search fourni
    if (search && search.trim()) {
      filter.$text = { $search: search.trim() };
    }

    const [total, data] = await Promise.all([
      Distributor.countDocuments(filter),
      Distributor.find(filter)
        .sort(search ? { score: { $meta: "textScore" } } : { createdAt: -1 })
        .skip((page - 1) * pageSize)
        .limit(pageSize),
    ]);

    return res.json({
      data,
      pagination: {
        page,
        pageSize,
        total,
        pages: Math.ceil(total / pageSize),
      },
    });
  } catch (err) {
    console.error("listDistributors error:", err);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};

/* GET ONE (public) */
exports.getDistributorById = async (req, res) => {
  try {
    const doc = await Distributor.findById(req.params.id);
    if (!doc) return res.status(404).json({ message: "Introuvable." });
    return res.json(doc);
  } catch (err) {
    console.error("getDistributorById error:", err);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};

/* UPDATE (admin) */
exports.updateDistributor = async (req, res) => {
  try {
    const doc = await Distributor.findById(req.params.id);
    if (!doc) return res.status(404).json({ message: "Introuvable." });

    const {
      name,
      contact,
      region,
      city,
      address,
      phone,
      whatsapp,
      latitude,
      longitude,
      hasStock,
      openingHours,
      notes,
      isActive,
    } = req.body;

    if (name !== undefined) doc.name = name;
    if (contact !== undefined) doc.contact = contact;
    if (region !== undefined) doc.region = region;
    if (city !== undefined) doc.city = city;
    if (address !== undefined) doc.address = address;
    if (phone !== undefined) doc.phone = phone;
    if (whatsapp !== undefined) doc.whatsapp = whatsapp;
    if (hasStock !== undefined) doc.hasStock = !!hasStock;
    if (openingHours !== undefined) doc.openingHours = openingHours;
    if (notes !== undefined) doc.notes = notes;
    if (isActive !== undefined) doc.isActive = !!isActive;

    // gestion géoloc : si les 2 fournis et valides → set ; si l’un est fourni mais pas l’autre → unset
    const lat = toNum(latitude);
    const lng = toNum(longitude);
    const latProvided = latitude !== undefined;
    const lngProvided = longitude !== undefined;

    if (latProvided || lngProvided) {
      if (lat !== undefined && lng !== undefined) {
        doc.location = { type: "Point", coordinates: [lng, lat] };
      } else {
        // on supprime si partiellement fourni / invalide
        doc.location = undefined;
      }
    }

    await doc.save();
    return res.json(doc);
  } catch (err) {
    console.error("updateDistributor error:", err);
    return res.status(500).json({ message: err.message || "Erreur serveur." });
  }
};

/* DELETE (admin) */
exports.deleteDistributor = async (req, res) => {
  try {
    const doc = await Distributor.findByIdAndDelete(req.params.id);
    if (!doc) return res.status(404).json({ message: "Introuvable." });
    return res.json({ success: true });
  } catch (err) {
    console.error("deleteDistributor error:", err);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};

/* NEARBY (public) — require lat/lng */
exports.listNearbyDistributors = async (req, res) => {
  try {
    const lat = toNum(req.query.lat);
    const lng = toNum(req.query.lng);
    const radiusKm = toNum(req.query.radiusKm) ?? 10;

    if (lat === undefined || lng === undefined) {
      return res.status(400).json({ message: "Paramètres lat/lng requis." });
    }

    const meters = Math.max(100, Math.min(radiusKm * 1000, 200000)); // 100m → 200km

    const data = await Distributor.aggregate([
      {
        $geoNear: {
          near: { type: "Point", coordinates: [lng, lat] },
          distanceField: "distanceMeters",
          maxDistance: meters,
          spherical: true,
          query: { isActive: true, location: { $exists: true } },
        },
      },
      { $sort: { distanceMeters: 1 } },
      { $limit: 100 },
    ]);

    return res.json({ data, radiusMeters: meters });
  } catch (err) {
    console.error("listNearbyDistributors error:", err);
    return res.status(500).json({ message: "Erreur serveur." });
  }
};
