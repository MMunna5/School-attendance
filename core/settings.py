"""
Django settings for core project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env", override=True)

from django.core.management.utils import get_random_secret_key

# Security: Load SECRET_KEY from environment
SECRET_KEY = os.environ.get("SECRET_KEY")

# DEBUG: Convert string to boolean safely, defaulting to False in production
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

if not SECRET_KEY:
    if DEBUG:
        # Dynamically generate a random secret key for local development
        SECRET_KEY = get_random_secret_key()
    else:
        raise ValueError("The SECRET_KEY environment variable must be set when DEBUG=False!")

# Hosts: Support comma-separated ALLOWED_HOSTS and Render external hostname
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(",") if host.strip()]

for dev_host in ["127.0.0.1", "localhost", "testserver"]:
    if dev_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(dev_host)

render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_host and render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_host)

# CSRF: Trusted origins for Render HTTPS proxy and custom domains
csrf_origins_env = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_env.split(",") if origin.strip()]
if render_host:
    render_origin = f"https://{render_host}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

# Inform Django that Render's reverse proxy terminates HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "attendance",
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# Database: Supabase PostgreSQL (via DATABASE_URL) with fallback to SQLite for local development
database_url = os.environ.get("DATABASE_URL")
if database_url:
    DATABASES = {
        "default": dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Dhaka"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images) handled by WhiteNoise
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# SMS and School configuration via environment variables
SMS_TOKEN = os.environ.get("SMS_TOKEN", "")
SCHOOL_SHORT_NAME = os.environ.get("SCHOOL_SHORT_NAME", "Shaheed Nur Hossain Memorial School")
SCHOOL_FULL_NAME = os.environ.get(
    "SCHOOL_FULL_NAME", "Shaheed Nur Hossain Memorial School, Biral, Dinajpur"
)

# Configurable initial password for bulk-uploaded teachers
DEFAULT_TEACHER_PASSWORD = os.environ.get("DEFAULT_TEACHER_PASSWORD", "12345")

# Production Security Hardening
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"