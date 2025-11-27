const nodemailer = require("nodemailer");
const dotenv = require("dotenv");

dotenv.config();

// Configuration du transporteur email
const createTransporter = () => {
  // Configuration pour Gmail (ou autre service SMTP)
  const transporter = nodemailer.createTransport({
    host: process.env.EMAIL_HOST || "smtp.gmail.com",
    port: process.env.EMAIL_PORT || 587,
    secure: false, // true pour 465, false pour les autres ports
    auth: {
      user: process.env.EMAIL_USER, // Votre adresse email
      pass: process.env.EMAIL_PASSWORD, // Votre mot de passe d'application Gmail
    },
    tls: {
      rejectUnauthorized: false, // Pour les environnements de développement
    },
  });

  return transporter;
};

/**
 * Envoie un email avec Nodemailer
 * @param {string} to - Adresse email du destinataire
 * @param {string} subject - Sujet de l'email
 * @param {string} html - Contenu HTML de l'email
 * @param {string} text - Contenu texte alternatif (optionnel)
 * @returns {Promise<{success: boolean, data?: any}>}
 */
const sendEmail = async (to, subject, html, text = null) => {
  try {
    // Vérifier que les variables d'environnement sont configurées
    if (!process.env.EMAIL_USER || !process.env.EMAIL_PASSWORD) {
      console.error("❌ Variables d'environnement EMAIL_USER et EMAIL_PASSWORD non configurées");
      return { success: false, error: "Configuration email manquante" };
    }

    const transporter = createTransporter();

    // Vérifier la connexion
    await transporter.verify();

    const mailOptions = {
      from: `"Fahimta" <${process.env.EMAIL_USER}>`,
      to,
      subject,
      html,
      text: text || html.replace(/<[^>]*>/g, ""), // Extraire le texte si html fourni
    };

    const info = await transporter.sendMail(mailOptions);

    console.log("✅ Email envoyé :", {
      to,
      subject,
      messageId: info.messageId,
    });

    return {
      success: true,
      data: {
        messageId: info.messageId,
        response: info.response,
      },
    };
  } catch (error) {
    console.error("❌ Erreur lors de l'envoi de l'email :", error.message);
    return {
      success: false,
      error: error.message,
    };
  }
};

/**
 * Envoie un code OTP par email
 * @param {string} to - Adresse email du destinataire
 * @param {string} otp - Code OTP à envoyer
 * @returns {Promise<{success: boolean}>}
 */
const sendOTPEmail = async (to, otp) => {
  const subject = "🔐 Code de vérification Fahimta";
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {
          font-family: Arial, sans-serif;
          line-height: 1.6;
          color: #333;
          max-width: 600px;
          margin: 0 auto;
          padding: 20px;
          background-color: #f4f4f4;
        }
        .container {
          background-color: #ffffff;
          border-radius: 10px;
          padding: 30px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
          text-align: center;
          margin-bottom: 30px;
        }
        .logo {
          font-size: 32px;
          font-weight: bold;
          color: #1976D2;
          margin-bottom: 10px;
        }
        .otp-box {
          background: linear-gradient(135deg, #1976D2 0%, #0f66c7 100%);
          color: #ffffff;
          padding: 20px;
          border-radius: 8px;
          text-align: center;
          margin: 30px 0;
        }
        .otp-code {
          font-size: 36px;
          font-weight: bold;
          letter-spacing: 8px;
          margin: 20px 0;
        }
        .footer {
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #e0e0e0;
          text-align: center;
          font-size: 12px;
          color: #666;
        }
        .warning {
          background-color: #fff3cd;
          border-left: 4px solid #ffc107;
          padding: 15px;
          margin: 20px 0;
          border-radius: 4px;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <div class="logo">📚 FAHIMTA</div>
          <p>Votre code de vérification</p>
        </div>
        
        <p>Bonjour,</p>
        
        <p>Vous avez demandé à créer un compte sur <strong>Fahimta</strong>. Utilisez le code suivant pour vérifier votre adresse email :</p>
        
        <div class="otp-box">
          <div class="otp-code">${otp}</div>
          <p style="margin: 0; font-size: 14px;">Ce code est valide pendant 5 minutes</p>
        </div>
        
        <div class="warning">
          <strong>⚠️ Important :</strong> Ne partagez jamais ce code avec personne. L'équipe Fahimta ne vous demandera jamais votre code de vérification.
        </div>
        
        <p>Si vous n'avez pas demandé ce code, vous pouvez ignorer cet email.</p>
        
        <div class="footer">
          <p>© ${new Date().getFullYear()} Fahimta. Tous droits réservés.</p>
          <p>Abokin karatun zamani. Ay zamani cewandika.</p>
        </div>
      </div>
    </body>
    </html>
  `;

  return await sendEmail(to, subject, html);
};

/**
 * Envoie un code de réinitialisation de mot de passe par email
 * @param {string} to - Adresse email du destinataire
 * @param {string} otp - Code OTP à envoyer
 * @returns {Promise<{success: boolean}>}
 */
const sendResetPasswordEmail = async (to, otp) => {
  const subject = "🔐 Réinitialisation de votre mot de passe Fahimta";
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {
          font-family: Arial, sans-serif;
          line-height: 1.6;
          color: #333;
          max-width: 600px;
          margin: 0 auto;
          padding: 20px;
          background-color: #f4f4f4;
        }
        .container {
          background-color: #ffffff;
          border-radius: 10px;
          padding: 30px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
          text-align: center;
          margin-bottom: 30px;
        }
        .logo {
          font-size: 32px;
          font-weight: bold;
          color: #1976D2;
          margin-bottom: 10px;
        }
        .otp-box {
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
          color: #ffffff;
          padding: 20px;
          border-radius: 8px;
          text-align: center;
          margin: 30px 0;
        }
        .otp-code {
          font-size: 36px;
          font-weight: bold;
          letter-spacing: 8px;
          margin: 20px 0;
        }
        .footer {
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #e0e0e0;
          text-align: center;
          font-size: 12px;
          color: #666;
        }
        .warning {
          background-color: #fee2e2;
          border-left: 4px solid #ef4444;
          padding: 15px;
          margin: 20px 0;
          border-radius: 4px;
        }
        .info {
          background-color: #dbeafe;
          border-left: 4px solid #3b82f6;
          padding: 15px;
          margin: 20px 0;
          border-radius: 4px;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <div class="logo">📚 FAHIMTA</div>
          <p>Réinitialisation de mot de passe</p>
        </div>
        
        <p>Bonjour,</p>
        
        <p>Vous avez demandé à réinitialiser votre mot de passe sur <strong>Fahimta</strong>. Utilisez le code suivant pour continuer :</p>
        
        <div class="otp-box">
          <div class="otp-code">${otp}</div>
          <p style="margin: 0; font-size: 14px;">Ce code est valide pendant 5 minutes</p>
        </div>
        
        <div class="warning">
          <strong>⚠️ Sécurité :</strong> Si vous n'avez pas demandé cette réinitialisation, ignorez cet email. Votre mot de passe ne sera pas modifié.
        </div>
        
        <div class="info">
          <strong>ℹ️ Note :</strong> Ne partagez jamais ce code avec personne. L'équipe Fahimta ne vous demandera jamais votre code de réinitialisation.
        </div>
        
        <p>Si vous avez des questions ou des préoccupations, n'hésitez pas à nous contacter.</p>
        
        <div class="footer">
          <p>© ${new Date().getFullYear()} Fahimta. Tous droits réservés.</p>
          <p>Abokin karatun zamani. Ay zamani cewandika.</p>
        </div>
      </div>
    </body>
    </html>
  `;

  return await sendEmail(to, subject, html);
};

/**
 * Envoie une notification de paiement réussi par email
 * @param {string} to - Adresse email du destinataire
 * @param {Object} paymentData - Données du paiement
 * @param {string} paymentData.amount - Montant payé
 * @param {string} paymentData.reference - Référence du paiement
 * @param {string} paymentData.method - Méthode de paiement (Carte, NITA, Code)
 * @param {Date} paymentData.subscriptionEnd - Date de fin d'abonnement
 * @param {string} paymentData.plan - Plan (mensuel/annuel)
 * @returns {Promise<{success: boolean}>}
 */
const sendPaymentConfirmationEmail = async (to, paymentData) => {
  const { amount, reference, method, subscriptionEnd, plan } = paymentData;
  
  const formatDate = (date) => {
    if (!date) return "N/A";
    const d = new Date(date);
    return d.toLocaleDateString("fr-FR", { 
      year: "numeric", 
      month: "long", 
      day: "numeric" 
    });
  };

  const formatAmount = (amt) => {
    return new Intl.NumberFormat("fr-FR", {
      style: "currency",
      currency: "XOF",
      minimumFractionDigits: 0,
    }).format(amt || 0);
  };

  const methodLabel = method === "NITA" ? "NITA" : method === "Carte" ? "Carte bancaire" : "Code d'accès";
  const planLabel = plan === "annuel" || (amount >= 15000) ? "Annuel" : "Mensuel";

  const subject = "✅ Confirmation de paiement - Fahimta";
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {
          font-family: Arial, sans-serif;
          line-height: 1.6;
          color: #333;
          max-width: 600px;
          margin: 0 auto;
          padding: 20px;
          background-color: #f4f4f4;
        }
        .container {
          background-color: #ffffff;
          border-radius: 10px;
          padding: 30px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
          text-align: center;
          margin-bottom: 30px;
        }
        .logo {
          font-size: 32px;
          font-weight: bold;
          color: #1976D2;
          margin-bottom: 10px;
        }
        .success-box {
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          color: #ffffff;
          padding: 20px;
          border-radius: 8px;
          text-align: center;
          margin: 30px 0;
        }
        .success-icon {
          font-size: 48px;
          margin-bottom: 10px;
        }
        .payment-details {
          background-color: #f9fafb;
          border-left: 4px solid #1976D2;
          padding: 20px;
          margin: 20px 0;
          border-radius: 4px;
        }
        .detail-row {
          display: flex;
          justify-content: space-between;
          padding: 10px 0;
          border-bottom: 1px solid #e5e7eb;
        }
        .detail-row:last-child {
          border-bottom: none;
        }
        .detail-label {
          font-weight: 600;
          color: #6b7280;
        }
        .detail-value {
          font-weight: 700;
          color: #111827;
        }
        .footer {
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #e0e0e0;
          text-align: center;
          font-size: 12px;
          color: #666;
        }
        .info {
          background-color: #dbeafe;
          border-left: 4px solid #3b82f6;
          padding: 15px;
          margin: 20px 0;
          border-radius: 4px;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <div class="logo">📚 FAHIMTA</div>
          <p>Confirmation de paiement</p>
        </div>
        
        <div class="success-box">
          <div class="success-icon">✅</div>
          <h2 style="margin: 0; font-size: 24px;">Paiement réussi !</h2>
          <p style="margin: 10px 0 0 0; font-size: 16px;">Votre abonnement a été activé avec succès</p>
        </div>
        
        <p>Bonjour,</p>
        
        <p>Nous vous confirmons que votre paiement a été traité avec succès. Votre abonnement <strong>Fahimta</strong> est maintenant actif.</p>
        
        <div class="payment-details">
          <h3 style="margin-top: 0; color: #1976D2;">Détails du paiement</h3>
          
          <div class="detail-row">
            <span class="detail-label">Montant payé :</span>
            <span class="detail-value">${formatAmount(amount)}</span>
          </div>
          
          <div class="detail-row">
            <span class="detail-label">Méthode de paiement :</span>
            <span class="detail-value">${methodLabel}</span>
          </div>
          
          <div class="detail-row">
            <span class="detail-label">Référence :</span>
            <span class="detail-value">${reference || "N/A"}</span>
          </div>
          
          <div class="detail-row">
            <span class="detail-label">Plan :</span>
            <span class="detail-value">${planLabel}</span>
          </div>
          
          <div class="detail-row">
            <span class="detail-label">Abonnement valide jusqu'au :</span>
            <span class="detail-value" style="color: #10b981;">${formatDate(subscriptionEnd)}</span>
          </div>
        </div>
        
        <div class="info">
          <strong>ℹ️ Information :</strong> Vous pouvez maintenant accéder à toutes les fonctionnalités premium de Fahimta jusqu'à la date d'expiration de votre abonnement.
        </div>
        
        <p>Merci de votre confiance et bonne continuation avec Fahimta !</p>
        
        <div class="footer">
          <p>© ${new Date().getFullYear()} Fahimta. Tous droits réservés.</p>
          <p>Abokin karatun zamani. Ay zamani cewandika.</p>
          <p style="margin-top: 10px; font-size: 11px; color: #999;">
            Si vous avez des questions, n'hésitez pas à nous contacter.
          </p>
        </div>
      </div>
    </body>
    </html>
  `;

  return await sendEmail(to, subject, html);
};

module.exports = { sendEmail, sendOTPEmail, sendResetPasswordEmail, sendPaymentConfirmationEmail };

