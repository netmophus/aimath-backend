# 🔌 Système de Chat Temps Réel avec Socket.io

## 📋 Vue d'ensemble

Le système de chat entre élèves et enseignants utilise maintenant **Socket.io** pour une communication en temps réel, similaire à WhatsApp.

---

## ✨ Fonctionnalités

### 1. **Messages instantanés**
- Les messages arrivent immédiatement sans rafraîchir
- Pas de délai, communication fluide

### 2. **Indicateur "En train d'écrire..."**
- Apparaît quand l'autre personne tape un message
- S'arrête automatiquement après 3 secondes d'inactivité
- Disparaît immédiatement à l'envoi

### 3. **Présence en ligne/hors ligne**
- Indicateur **🟢 En ligne** si la personne est connectée
- Indicateur **⚪ Hors ligne** si déconnectée
- Mise à jour en temps réel

### 4. **Système de rooms**
- Chaque conversation a sa propre "room"
- Format: `userId1-userId2` (trié alphabétiquement)
- Seuls les participants reçoivent les messages

---

## 🏗️ Architecture

### Backend (`server.js` + `socket/socketHandler.js`)

**Événements émis par le serveur:**
- `user:online` - Notifie qu'un utilisateur est en ligne
- `user:offline` - Notifie qu'un utilisateur est hors ligne
- `message:received` - Nouveau message reçu
- `message:notification` - Notification de message (si pas dans la conversation)
- `typing:active` - Quelqu'un est en train d'écrire
- `typing:inactive` - A arrêté d'écrire

**Événements reçus par le serveur:**
- `chat:join` - Rejoindre une room de conversation
- `chat:leave` - Quitter une room
- `message:send` - Envoyer un message
- `typing:start` - Commencer à écrire
- `typing:stop` - Arrêter d'écrire
- `user:check-online` - Vérifier si un utilisateur est en ligne

### Frontend (`hooks/useSocket.js`)

**Hook custom `useSocket(token)`**

Retourne:
- `isConnected` - Statut de connexion Socket.io
- `onlineUsers` - Set des IDs d'utilisateurs en ligne
- `joinChat(userId)` - Rejoindre une conversation
- `leaveChat(userId)` - Quitter une conversation
- `sendMessage(to, message)` - Envoyer un message via Socket
- `startTyping(to)` - Indiquer qu'on écrit
- `stopTyping(to)` - Arrêter l'indicateur
- `onMessage(callback)` - S'abonner aux nouveaux messages
- `onTyping(callback)` - S'abonner aux événements typing

---

## 🔒 Sécurité

### Authentification
- Token JWT requis pour toutes les connexions Socket.io
- Middleware d'authentification sur chaque connexion
- Validation de l'utilisateur via la base de données

### Autorisation
- Seuls les utilisateurs avec sessions actives peuvent communiquer
- Vérification via `SupportRequest` (status: "acceptee", sessionStarted: true)

---

## 🚀 Utilisation

### Côté Élève (`StudentChatPage.jsx`)
```javascript
const { isConnected, onlineUsers, sendMessage, onMessage } = useSocket(token);

// Vérifier si l'enseignant est en ligne
const teacherOnline = onlineUsers.has(teacher._id);

// Envoyer un message
sendMessage(teacher._id, messageObject);

// Écouter les nouveaux messages
useEffect(() => {
  const unsubscribe = onMessage((message) => {
    setMessages(prev => [...prev, message]);
  });
  return unsubscribe;
}, []);
```

### Côté Enseignant (`TeacherChatPage.jsx`)
```javascript
const { isConnected, onlineUsers, sendMessage, onMessage } = useSocket(token);

// Vérifier si l'élève est en ligne
const studentOnline = onlineUsers.has(student._id);

// Même logique que côté élève
```

---

## 📊 Flux de données

### Envoi de message:
1. User tape un message
2. Appelle `handleSend()`
3. Envoie via API REST → sauvegarde en DB
4. Envoie via Socket.io → livraison instantanée
5. Le destinataire reçoit via `message:received`
6. Interface mise à jour immédiatement

### Indicateur "En train d'écrire":
1. User commence à taper
2. `startTyping(otherUserId)` est appelé
3. Événement `typing:start` envoyé au serveur
4. Serveur transmet `typing:active` au destinataire
5. Interface du destinataire affiche "En train d'écrire..."
6. Auto-stop après 3 secondes d'inactivité

---

## 🧪 Tests

### Tester la connexion temps réel:
1. Ouvrir 2 navigateurs différents
2. Se connecter en tant qu'élève (navigateur 1)
3. Se connecter en tant qu'enseignant (navigateur 2)
4. Vérifier que les statuts "En ligne" sont corrects
5. Envoyer un message → doit apparaître instantanément
6. Taper un message → "En train d'écrire..." doit apparaître

---

## ⚡ Performance

- Reconnexion automatique en cas de perte de connexion
- Max 5 tentatives de reconnexion
- Délai de 1 seconde entre chaque tentative
- Nettoyage automatique des indicateurs "typing" après 5 secondes
- Transports: WebSocket (prioritaire) + Polling (fallback)

---

## 🐛 Troubleshooting

### "Socket.io ne se connecte pas"
- Vérifier que le serveur backend est démarré
- Vérifier l'URL dans `api.js` (ligne 6)
- Vérifier les CORS dans `server.js` (ligne 25-35)
- Vérifier le token JWT dans localStorage

### "Messages en double"
- Le système évite les doublons via check de `_id`
- Si problème persiste, vider le cache navigateur

### "Indicateur 'En train d'écrire' reste bloqué"
- Nettoyage automatique après 5 secondes
- Redémarrer le serveur si nécessaire

---

## 📝 Notes importantes

- Socket.io utilise le même PORT que l'API Express (5000 par défaut)
- Les messages sont TOUJOURS sauvegardés en DB (via API REST)
- Socket.io est une couche de notification instantanée en plus
- Rétrocompatible: fonctionne même si Socket.io échoue
