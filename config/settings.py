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
IA_MODELE = config('IA_MODELE', default='claude-sonnet-5')
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

# Notion de la leçon 13 ("Fonction logarithme népérien"), leçon MODÈLE
# utilisée en few-shot dans les prompts de génération (voir programme/ia/prompts.py).
IA_NOTION_MODELE_ID = config('IA_NOTION_MODELE_ID', default=49, cast=int)