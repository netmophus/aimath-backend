from datetime import timedelta
from pathlib import Path
import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# '.ngrok-free.app' et '.ngrok.io' : TEST NGROK (réversible) — un point en
# préfixe autorise tout sous-domaine (Django ALLOWED_HOSTS). Les requêtes
# arrivent ici relayées par le rewrite Next.js (voir next.config.ts) donc
# réseau-parlant c'est toujours 127.0.0.1, mais l'en-tête Host transmis peut
# selon les cas porter le nom d'hôte ngrok d'origine — on couvre les deux
# pour éviter un blocage "Invalid HTTP_HOST". À retirer avec le reste du
# test ngrok si non utilisé au quotidien.
#
# ALLOWED_HOSTS_SUPPLEMENTAIRES : domaine(s) réel(s) de l'hébergeur en prod
# (ex. "fahimtana-backend.herokuapp.com"), une liste séparée par des
# virgules — jamais en dur ici, pour ne pas coder un domaine spécifique à un
# hébergeur dans le code source.
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '.ngrok-free.app', '.ngrok.io'] + [
    hote.strip()
    for hote in config('ALLOWED_HOSTS_SUPPLEMENTAIRES', default='').split(',')
    if hote.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Bibliothèques tierces
    'rest_framework',
    'corsheaders',
    'cloudinary_storage',
    'cloudinary',

    # Apps métier
    'programme',
    'comptes',
    'budget_ia',
    'traitement_ia',
]

AUTH_USER_MODEL = 'comptes.User'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',          # doit être haut
    'django.middleware.security.SecurityMiddleware',
    # Juste après SecurityMiddleware (exigence Whitenoise) : sert les
    # fichiers statiques collectés (STATIC_ROOT) directement depuis
    # gunicorn, sans serveur front (nginx/CDN) séparé — suffisant pour
    # l'admin Django et les quelques assets statiques de l'API.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# DATABASE_URL (format postgres://user:password@host:port/nom) : c'est ce
# que fournissent Heroku et la plupart des hébergeurs Postgres managés. Si
# elle est définie, elle prime — sinon on retombe sur les variables DB_*
# existantes (dev local), pour ne rien casser de la config actuelle.
_DATABASE_URL = config('DATABASE_URL', default='')
if _DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(_DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='127.0.0.1'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Niamey'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
# Cible de `manage.py collectstatic` — Whitenoise sert ce dossier en prod
# (voir MIDDLEWARE). CompressedManifestStaticFilesStorage : fichiers
# hashés + gzip/brotli, sûr à mettre en cache indéfiniment côté navigateur.
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Cloudinary (photo de profil élève, comptes.User.photo — voir ce champ).
# Le système de fichiers d'Heroku est éphémère : les fichiers uploadés
# localement (MEDIA_ROOT ci-dessus) disparaissent à chaque redéploiement,
# d'où Cloudinary pour ce champ précis. CLOUDINARY_CONFIGURE est False tant
# que les 3 variables ne sont pas toutes renseignées (cas du dev local par
# défaut) : le champ `photo` retombe alors silencieusement sur le stockage
# local (voir CloudinaryField, comptes/models.py) plutôt que de planter —
# aucun appel réseau à Cloudinary n'est jamais tenté sans identifiants.
CLOUDINARY_CLOUD_NAME = config('CLOUDINARY_CLOUD_NAME', default='')
CLOUDINARY_API_KEY = config('CLOUDINARY_API_KEY', default='')
CLOUDINARY_API_SECRET = config('CLOUDINARY_API_SECRET', default='')
CLOUDINARY_CONFIGURE = bool(
    CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET
)
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
    'API_KEY': CLOUDINARY_API_KEY,
    'API_SECRET': CLOUDINARY_API_SECRET,
}
if CLOUDINARY_CONFIGURE:
    import cloudinary as _cloudinary

    _cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS — autoriser le front Next.js. FRONTEND_URL : une ou plusieurs
# origines du frontend déployé, séparées par des virgules (ex.
# "https://fahimtana.herokuapp.com,https://myfahimta.com,https://www.myfahimta.com"),
# jamais codées en dur ici pour ne pas lier ce fichier à un domaine précis.
_FRONTEND_URLS = config('FRONTEND_URL', default='')
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    # 3001 : port de repli de `next dev` quand 3000 est déjà occupé sur la
    # machine de dev — arrive régulièrement, éviter un blocage CORS silencieux.
    'http://localhost:3001',
    'http://127.0.0.1:3001',
] + [origine.strip() for origine in _FRONTEND_URLS.split(',') if origine.strip()]

# Durcissement HTTPS — seulement quand DEBUG=False, pour ne pas casser le
# dev local en clair (http://127.0.0.1:8001). SECURE_PROXY_SSL_HEADER est
# nécessaire sur Heroku (et la plupart des PaaS) : le routeur termine le
# HTTPS et relaie en HTTP en interne avec cet en-tête — sans ce réglage,
# Django croit chaque requête non sécurisée et SECURE_SSL_REDIRECT boucle.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # 7 jours pour commencer (voir avertissement Django security.W004) : à
    # augmenter (ex. 31536000 = 1 an) une fois HTTPS confirmé stable partout.
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Configuration REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Configuration JWT (djangorestframework-simplejwt)
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=45),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# --- Génération IA (programme.ia) ---
# Fournisseur interchangeable : voir programme/ia/fournisseurs.py, qui lit
# ces réglages plutôt que de coder "anthropic" en dur. Changer de
# fournisseur/modèle ne touche donc qu'au .env, jamais au code.
IA_FOURNISSEUR = config('IA_FOURNISSEUR', default='anthropic')
# claude-sonnet-5 : bon compromis qualité de rédaction / coût pour un usage
# répété (un appel = une section de leçon). À ajuster ici si besoin.
IA_MODELE = config('IA_MODELE', default='claude-sonnet-5-5')
IA_TIMEOUT_SECONDES = config('IA_TIMEOUT_SECONDES', default=180, cast=int)
# 16000 : claude-sonnet-5 consomme une partie du budget de sortie en tokens
# de "réflexion" interne avant de produire le texte final — 4096 puis 8192
# se sont avérés insuffisants en pratique (cours/exercices tronqués). Ce
# modèle accepte jusqu'à 128 000 tokens de sortie, mais au-delà d'environ
# 21 000 le SDK Anthropic exige le streaming (non utilisé ici) sous peine de
# timeout HTTP côté client — 16000 reste donc sûr en appel non-streaming tout
# en doublant la marge par rapport à l'ancienne valeur. Si la troncature
# revient (voir GenererSectionView, champ "tronque"), il faudra passer ce
# endpoint en streaming plutôt que remonter encore ce chiffre.
IA_MAX_TOKENS_REPONSE = config('IA_MAX_TOKENS_REPONSE', default=16000, cast=int)
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')

# --- Lecture/analyse des exercices déposés (programme.lecture_exercice) ----
# DÉSACTIVÉE PAR DÉFAUT : chaque analyse est un appel Anthropic facturé, avec
# images/PDF. IA_LECTURE_DEV_SEULEMENT (vrai par défaut) la restreint en plus
# à DEBUG=True : même avec IA_LECTURE_ACTIVE=True, rien ne part tant que le
# serveur n'est pas en mode développement. Pour ouvrir à tous les élèves plus
# tard : IA_LECTURE_ACTIVE=True ET IA_LECTURE_DEV_SEULEMENT=False.
IA_LECTURE_ACTIVE = config('IA_LECTURE_ACTIVE', default=False, cast=bool)
IA_LECTURE_DEV_SEULEMENT = config('IA_LECTURE_DEV_SEULEMENT', default=True, cast=bool)
# Vide = réutilise IA_MODELE (le modèle doit accepter images et PDF).
IA_LECTURE_MODELE = config('IA_LECTURE_MODELE', default='')
IA_LECTURE_MAX_TOKENS = config('IA_LECTURE_MAX_TOKENS', default=8000, cast=int)
IA_LECTURE_TIMEOUT_SECONDES = config('IA_LECTURE_TIMEOUT_SECONDES', default=120, cast=int)
# Durée de conservation de l'ANALYSE (texte) pour ne pas refacturer un même
# exercice renvoyé (double clic, nouvelle tentative). Les photos ne sont jamais gardées.
IA_LECTURE_CACHE_SECONDES = config('IA_LECTURE_CACHE_SECONDES', default=3600, cast=int)

# --- Correction complète des exercices de maths (programme.correction) ----
# DÉSACTIVÉE PAR DÉFAUT : chaque correction est un appel Anthropic facturé,
# suivi (au plus) de requêtes Wolfram Alpha. Même règle que la lecture :
# IA_CORRECTION_DEV_SEULEMENT (vrai par défaut) exige DEBUG=True.
IA_CORRECTION_ACTIVE = config('IA_CORRECTION_ACTIVE', default=False, cast=bool)
IA_CORRECTION_DEV_SEULEMENT = config('IA_CORRECTION_DEV_SEULEMENT', default=True, cast=bool)
IA_CORRECTION_MODELE = config('IA_CORRECTION_MODELE', default='')  # vide = IA_MODELE
IA_CORRECTION_MAX_TOKENS = config('IA_CORRECTION_MAX_TOKENS', default=12000, cast=int)
IA_CORRECTION_TIMEOUT_SECONDES = config('IA_CORRECTION_TIMEOUT_SECONDES', default=180, cast=int)
IA_CORRECTION_CACHE_SECONDES = config('IA_CORRECTION_CACHE_SECONDES', default=3600, cast=int)
# --- Simulations interactives GeoGebra dans la correction (étape 9.1) ----
# DÉSACTIVÉES PAR DÉFAUT et réservées au développement local tant que la licence commerciale GeoGebra n'est
# pas finalisée : SIMULATIONS_DEV_SEULEMENT (vrai par défaut) exige DEBUG=True. Aucune IA n'est appelée.
SIMULATIONS_ACTIVES = config('SIMULATIONS_ACTIVES', default=False, cast=bool)
SIMULATIONS_DEV_SEULEMENT = config('SIMULATIONS_DEV_SEULEMENT', default=True, cast=bool)
# App ID Wolfram Alpha (vide = le contrôle Wolfram est ignoré, SymPy reste utilisé).
WOLFRAM_APP_ID = config('WOLFRAM_APP_ID', default='')
WOLFRAM_TIMEOUT_SECONDES = config('WOLFRAM_TIMEOUT_SECONDES', default=20, cast=int)

# --- Professeur particulier IA (programme.professeur) ----------------------
# DÉSACTIVÉ PAR DÉFAUT, même règle que la lecture et la correction : réservé
# à DEBUG=True tant que IA_PROF_DEV_SEULEMENT est vrai. Les séances sont
# TEMPORAIRES (cache Django, expiration IA_PROF_SEANCE_SECONDES), jamais en base.
IA_PROF_ACTIVE = config('IA_PROF_ACTIVE', default=False, cast=bool)
IA_PROF_DEV_SEULEMENT = config('IA_PROF_DEV_SEULEMENT', default=True, cast=bool)
IA_PROF_MODELE = config('IA_PROF_MODELE', default='')  # vide = IA_MODELE
IA_PROF_MAX_TOKENS_PLAN = config('IA_PROF_MAX_TOKENS_PLAN', default=14000, cast=int)
IA_PROF_MAX_TOKENS_TOUR = config('IA_PROF_MAX_TOKENS_TOUR', default=1200, cast=int)
IA_PROF_TIMEOUT_SECONDES = config('IA_PROF_TIMEOUT_SECONDES', default=150, cast=int)
IA_PROF_SEANCE_SECONDES = config('IA_PROF_SEANCE_SECONDES', default=7200, cast=int)
IA_PROF_PLAN_CACHE_SECONDES = config('IA_PROF_PLAN_CACHE_SECONDES', default=3600, cast=int)
IA_PROF_MAX_APPELS_IA = config('IA_PROF_MAX_APPELS_IA', default=40, cast=int)       # par séance
IA_PROF_MAX_ECHANGES = config('IA_PROF_MAX_ECHANGES', default=80, cast=int)         # actions de l'élève par séance
IA_PROF_MAX_SEANCES_PAR_HEURE = config('IA_PROF_MAX_SEANCES_PAR_HEURE', default=6, cast=int)  # par élève

# Notion de la leçon 13 ("Fonction logarithme népérien"), leçon MODÈLE
# utilisée en few-shot dans les prompts de génération (voir programme/ia/prompts.py).
IA_NOTION_MODELE_ID = config('IA_NOTION_MODELE_ID', default=49, cast=int)

# --- Paiement NITA (voir comptes/nita.py, comptes/nita_views.py) ---------
# Défauts VIDES uniquement (jamais une vraie valeur en dur) : un appel réel
# sans configuration échoue proprement via NitaError plutôt que d'utiliser
# une clé secrète codée en dur.
NITA_BASE_URL = config('NITA_BASE_URL', default='')
NITA_API_KEY = config('NITA_API_KEY', default='')
NITA_USERNAME = config('NITA_USERNAME', default='')
NITA_PASSWORD = config('NITA_PASSWORD', default='')
NITA_TIMEOUT_SECONDES = config('NITA_TIMEOUT_SECONDES', default=20, cast=int)
# Mode simulé (aucun appel réseau réel vers NITA, voir comptes/nita.py) —
# UNIQUEMENT pour les tests locaux. JAMAIS à activer en production.
NITA_MOCK = config('NITA_MOCK', default=False, cast=bool)

# --- SMS LAM / LAMPUSH (voir comptes/sms.py) ------------------------------
# Défauts VIDES uniquement (jamais une vraie valeur en dur).
LAM_SMS_URL = config('LAM_SMS_URL', default='https://lamsms.lafricamobile.com/api')
LAM_ACCOUNTID = config('LAM_ACCOUNTID', default='')
LAM_PASSWORD = config('LAM_PASSWORD', default='')
LAM_DEFAULT_SENDER = config('LAM_DEFAULT_SENDER', default='')
# Mode simulé (aucun appel réseau réel vers LAM, logge le SMS à la place,
# voir comptes/sms.py) — UNIQUEMENT pour les tests locaux, JAMAIS en
# production. Distinct de NITA_MOCK (deux intégrations indépendantes).
SMS_MOCK = config('SMS_MOCK', default=False, cast=bool)

# Sans ceci, les logger.info()/logger.error() de comptes/sms.py (et
# comptes/nita.py) n'atteignent nulle part : Python n'a par défaut qu'un
# handler "de secours" sur stderr qui ne montre QUE WARNING et plus —
# indispensable pour voir les envois SMS_MOCK/les échecs LAM en dev comme
# en prod (logs Heroku). INFO en dev (DEBUG=True), WARNING seulement en
# prod pour ne pas noyer les logs de routine.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'comptes': {
            'handlers': ['console'],
            'level': 'INFO' if DEBUG else 'WARNING',
            'propagate': False,
        },
    },
}

# ---------------------------------------------------------------------------
#  Budget IA (app budget_ia) : plafond GLOBAL mensuel, quotas par élève, interrupteur.
#  Montants = ESTIMATIONS internes en FCFA (jamais la facture Anthropic). Tout est réglable par variable d'environnement.
# ---------------------------------------------------------------------------
# Interrupteur global : False coupe TOUS les appels Anthropic (lecture, correction, fahimta ai, contenu admin)
# sans toucher aux autres fonctionnalités. Les trois IA_*_ACTIVE restent nécessaires en plus.
IA_INTERRUPTEUR_GLOBAL = config('IA_INTERRUPTEUR_GLOBAL', default=True, cast=bool)
BUDGET_IA_MENSUEL_FCFA = config('BUDGET_IA_MENSUEL_FCFA', default=100000, cast=int)       # plafond de référence
BUDGET_IA_SEUIL_OPERATIONNEL_FCFA = config('BUDGET_IA_SEUIL_OPERATIONNEL_FCFA', default=90000, cast=int)  # blocage réel
# Taux USD/FCFA : valeur PRUDENTE (au-dessus de la fourchette observée 574 à 597 en juillet 2026, sources non officielles).
# À réviser régulièrement : c'est un réglage, pas une constante.
IA_TAUX_USD_FCFA = config('IA_TAUX_USD_FCFA', default='600')
IA_TAUX_USD_FCFA_DATE = config('IA_TAUX_USD_FCFA_DATE', default='2026-11-03')
IA_MARGE_SECURITE = config('IA_MARGE_SECURITE', default='0.10')   # +10 % sur tous les coûts estimés
# Référence BCEAO du 2026-11-03 : cours vendeur USD 589,25 FCFA (transferts). Information : le taux retenu ci-dessus (600) reste plus prudent.
IA_TAUX_BCEAO_REFERENCE = config('IA_TAUX_BCEAO_REFERENCE', default='589.25')
IA_TAUX_BCEAO_DATE = config('IA_TAUX_BCEAO_DATE', default='2026-11-03')
IA_TARIFS_USD = config('IA_TARIFS_USD', default='', cast=lambda v: __import__('json').loads(v) if v else None)
# Quotas par élève (fuseau Africa/Niamey pour le jour).
IA_EXERCICES_PAR_JOUR = config('IA_EXERCICES_PAR_JOUR', default=3, cast=int)
IA_INTERACTIONS_PROF_PAR_EXERCICE = config('IA_INTERACTIONS_PROF_PAR_EXERCICE', default=10, cast=int)
IA_LECTURES_MAX_PAR_EXERCICE = config('IA_LECTURES_MAX_PAR_EXERCICE', default=3, cast=int)       # 1 lecture + 2 relectures
IA_CORRECTIONS_MAX_PAR_EXERCICE = config('IA_CORRECTIONS_MAX_PAR_EXERCICE', default=2, cast=int)
IA_PLANS_MAX_PAR_EXERCICE = config('IA_PLANS_MAX_PAR_EXERCICE', default=2, cast=int)
# Plafond de tokens de sortie d'une réponse conversationnelle (fahimta ai). Les sorties structurées d'un seul coup
# (lecture, correction, plan) gardent leurs plafonds propres : 4000 les tronquerait.
IA_MAX_TOKENS_SORTIE_PAR_REPONSE = config('IA_MAX_TOKENS_SORTIE_PAR_REPONSE', default=4000, cast=int)
# Estimation PRUDENTE des tokens d'entrée avant l'appel (réservation).
IA_EST_CARACTERES_PAR_TOKEN = config('IA_EST_CARACTERES_PAR_TOKEN', default='2.5')
IA_EST_TOKENS_PAR_IMAGE = config('IA_EST_TOKENS_PAR_IMAGE', default=5000, cast=int)   # doc vision : ceil(l/28) x ceil(h/28), plafond selon le modèle : réserve large
IA_EST_TOKENS_PAR_PAGE_PDF = config('IA_EST_TOKENS_PAR_PAGE_PDF', default=3500, cast=int)
IA_EST_TOKENS_FIXES = config('IA_EST_TOKENS_FIXES', default=1500, cast=int)   # consignes + schéma d'outil


# ---------------------------------------------------------------------------
#  Cache PARTAGÉ (PostgreSQL) : séances fahimta ai, verrous anti double envoi, résultats mis en cache.
#  Le cache par défaut de Django (mémoire locale) est propre à CHAQUE processus : avec plusieurs workers gunicorn, un
#  second dyno ou un redémarrage, les séances disparaissaient et les verrous ne protégeaient plus rien. La table
#  `cache_fahimta` est créée par la migration traitement_ia.0002. MAX_ENTRIES très haut : jamais d'éviction anticipée.
#  Redis n'est pas nécessaire à ce volume (quelques dizaines d'élèves) : une base de plus à payer pour rien.
# ---------------------------------------------------------------------------
if config('CACHE_BACKEND', default='db') == 'locmem':   # tests rapides / debug uniquement
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'cache_fahimta',
            'OPTIONS': {'MAX_ENTRIES': 100000, 'CULL_FREQUENCY': 3},
        }
    }

# ---------------------------------------------------------------------------
#  Traitement asynchrone des appels IA longs (app traitement_ia, process type Heroku `worker`).
#  False = ancien comportement synchrone (développement, tests). En production : True, et un dyno worker DOIT tourner.
# ---------------------------------------------------------------------------
IA_TRAITEMENT_ASYNCHRONE = config('IA_TRAITEMENT_ASYNCHRONE', default=False, cast=bool)
IA_TACHES_ACTIVES_MAX_PAR_ELEVE = config('IA_TACHES_ACTIVES_MAX_PAR_ELEVE', default=3, cast=int)
IA_TACHE_TENTATIVES_MAX = config('IA_TACHE_TENTATIVES_MAX', default=2, cast=int)
# Une réservation budgétaire laissée ouverte (processus tué) est soldée après cette durée ; le bail d'une tâche est plus
# long, pour qu'une reprise ne soit jamais refusée comme « double envoi » par sa propre réservation périmée.
IA_RESERVATION_PEREMPTION_SECONDS = config('IA_RESERVATION_PEREMPTION_SECONDS', default=420, cast=int)
IA_TACHE_BAIL_SECONDES = config('IA_TACHE_BAIL_SECONDES', default=480, cast=int)
IA_TACHE_RESULTAT_SECONDES = config('IA_TACHE_RESULTAT_SECONDES', default=7200, cast=int)  # résultat conservé 2 h
# Après expiration, seule une trace SANS contenu reste 24 h : l'élève lit « résultat expiré » au lieu d'un silence.
IA_TACHE_TRACE_SECONDES = config('IA_TACHE_TRACE_SECONDES', default=86400, cast=int)
IA_WORKER_THREADS = config('IA_WORKER_THREADS', default=4, cast=int)
IA_WORKER_INTERVALLE_SECONDES = config('IA_WORKER_INTERVALLE_SECONDES', default='0.5')
