// socket/socketHandler.js
const jwt = require("jsonwebtoken");
const User = require("../models/userModel");

// Store des utilisateurs connectés { userId: socketId }
const connectedUsers = new Map();

// Store des utilisateurs en train d'écrire { conversationKey: { userId, timestamp } }
const typingUsers = new Map();

module.exports = (io) => {
  // ✅ Middleware d'authentification Socket.io
  io.use(async (socket, next) => {
    try {
      const token = socket.handshake.auth.token || socket.handshake.headers.authorization?.split(" ")[1];
      
      if (!token) {
        return next(new Error("Authentication error: No token provided"));
      }

      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      const user = await User.findById(decoded.id).select("-password");

      if (!user) {
        return next(new Error("Authentication error: User not found"));
      }

      socket.userId = user._id.toString();
      socket.userRole = user.role;
      socket.userName = user.fullName;
      
      next();
    } catch (err) {
      console.error("Socket auth error:", err.message);
      next(new Error("Authentication error"));
    }
  });

  // ✅ Connexion d'un utilisateur
  io.on("connection", (socket) => {
    console.log(`🔌 Utilisateur connecté: ${socket.userName} (${socket.userId})`);
    
    // Enregistrer l'utilisateur comme connecté
    connectedUsers.set(socket.userId, socket.id);
    
    // Notifier tous les autres utilisateurs qu'il est en ligne
    socket.broadcast.emit("user:online", { userId: socket.userId });

    // ✅ Rejoindre une room de conversation
    socket.on("chat:join", ({ otherUserId }) => {
      const roomId = [socket.userId, otherUserId].sort().join("-");
      socket.join(roomId);
      console.log(`📥 ${socket.userName} a rejoint la room: ${roomId}`);
    });

    // ✅ Quitter une room
    socket.on("chat:leave", ({ otherUserId }) => {
      const roomId = [socket.userId, otherUserId].sort().join("-");
      socket.leave(roomId);
      console.log(`📤 ${socket.userName} a quitté la room: ${roomId}`);
    });

    // ✅ Nouveau message envoyé
    socket.on("message:send", ({ to, message }) => {
      const roomId = [socket.userId, to].sort().join("-");
      
      // Envoyer au destinataire via la room
      io.to(roomId).emit("message:received", message);
      
      // Notifier le destinataire s'il n'est pas dans la conversation
      const recipientSocketId = connectedUsers.get(to);
      if (recipientSocketId) {
        io.to(recipientSocketId).emit("message:notification", {
          from: socket.userId,
          fromName: socket.userName,
          snippet: message.text?.substring(0, 50) || "📎 Fichier",
        });
      }
      
      console.log(`💬 Message de ${socket.userName} vers ${to}`);
    });

    // ✅ Message supprimé
    socket.on("message:delete", ({ to, messageId }) => {
      const roomId = [socket.userId, to].sort().join("-");
      
      // Notifier tous les participants de la room (y compris l'expéditeur)
      io.to(roomId).emit("message:deleted", { messageId });
      
      console.log(`🗑️ Message ${messageId} supprimé par ${socket.userName}`);
    });

    // ✅ Indicateur "en train d'écrire..."
    socket.on("typing:start", ({ to }) => {
      const roomId = [socket.userId, to].sort().join("-");
      typingUsers.set(roomId, { userId: socket.userId, timestamp: Date.now() });
      
      // Notifier l'autre utilisateur
      const recipientSocketId = connectedUsers.get(to);
      if (recipientSocketId) {
        io.to(recipientSocketId).emit("typing:active", { 
          from: socket.userId,
          fromName: socket.userName 
        });
      }
    });

    socket.on("typing:stop", ({ to }) => {
      const roomId = [socket.userId, to].sort().join("-");
      typingUsers.delete(roomId);
      
      // Notifier l'autre utilisateur
      const recipientSocketId = connectedUsers.get(to);
      if (recipientSocketId) {
        io.to(recipientSocketId).emit("typing:inactive", { 
          from: socket.userId 
        });
      }
    });

    // ✅ Vérifier qui est en ligne
    socket.on("user:check-online", ({ userId }, callback) => {
      const isOnline = connectedUsers.has(userId);
      if (callback) callback({ isOnline });
    });

    // ✅ Déconnexion
    socket.on("disconnect", () => {
      console.log(`🔌 Utilisateur déconnecté: ${socket.userName} (${socket.userId})`);
      
      // Retirer l'utilisateur de la liste des connectés
      connectedUsers.delete(socket.userId);
      
      // Notifier tous les autres qu'il est hors ligne
      socket.broadcast.emit("user:offline", { userId: socket.userId });
      
      // Nettoyer les indicateurs "en train d'écrire"
      for (const [roomId, data] of typingUsers.entries()) {
        if (data.userId === socket.userId) {
          typingUsers.delete(roomId);
        }
      }
    });
  });

  // Nettoyage périodique des indicateurs "en train d'écrire" (après 5 secondes d'inactivité)
  setInterval(() => {
    const now = Date.now();
    for (const [roomId, data] of typingUsers.entries()) {
      if (now - data.timestamp > 5000) {
        typingUsers.delete(roomId);
      }
    }
  }, 2000);

  console.log("✅ Socket.io handler initialisé");
};
