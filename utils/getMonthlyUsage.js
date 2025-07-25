const MonthlyUsage = require("../models/MonthlyUsage");

const getCurrentPeriod = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
};

const getOrCreateMonthlyUsage = async (userId) => {
  const period = getCurrentPeriod();

  let usage = await MonthlyUsage.findOne({ user: userId, period });
  if (!usage) {
    usage = await MonthlyUsage.create({ user: userId, period });
  }

  return usage;
};

module.exports = { getOrCreateMonthlyUsage };
