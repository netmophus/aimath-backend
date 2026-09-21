from datetime import timedelta
from pathlib import Path
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
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '.ngrok-free.app', '.ngrok.io']

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

    # Apps métier
    'programme',
    'comptes',
]

AUTH_USER_MODEL = 'comptes.User'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',          # doit être haut
    'django.middleware.security.SecurityMiddleware',
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
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS — autoriser le front Next.js
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

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
IA_TIMEOUT_SECONDES = config('IA_TIMEOUT_SECONDES', default=90, cast=int)
# 8192 : claude-sonnet-5 consomme une partie du budget de sortie en tokens
# de "réflexion" interne avant de produire le texte final — 4096 s'est avéré
# insuffisant en pratique (réponse JSON tronquée pour la section exercices).
IA_MAX_TOKENS_REPONSE = config('IA_MAX_TOKENS_REPONSE', default=8192, cast=int)
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')

# Notion de la leçon 13 ("Fonction logarithme népérien"), leçon MODÈLE
# utilisée en few-shot dans les prompts de génération (voir programme/ia/prompts.py).
IA_NOTION_MODELE_ID = config('IA_NOTION_MODELE_ID', default=49, cast=int)