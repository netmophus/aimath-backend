


const axios = require("axios");
const dotenv = require("dotenv");

dotenv.config();

const SMS_API_URL = process.env.SMS_API_URL;
const SMS_USERNAME = process.env.SMS_USERNAME;
const SMS_PASSWORD = process.env.SMS_PASSWORD;

const sendSMS = async (to, message) => {
  try {
    const payload = {
      to,
      from: "Softlink",
      content: message,
      dlr: "yes",
      "dlr-level": 3,
      "dlr-method": "GET",
      "dlr-url": "https://sms.ne/dlr",
    };

    const response = await axios.post(SMS_API_URL, payload, {
      auth: {
        username: SMS_USERNAME,
        password: SMS_PASSWORD,
      },
      headers: {
        "Content-Type": "application/json",
      },
    });

    console.log("✅ SMS envoyé :", response.data);

    return response.status === 200
      ? { success: true, data: response.data }
      : { success: false, data: response.data };

  } catch (error) {
    if (error.response) {
      console.error("❌ Erreur de l'API SMS :", error.response.data);
    } else {
      console.error("❌ Erreur réseau :", error.message);
    }
    return { success: false };
  }
};

module.exports = { sendSMS };
