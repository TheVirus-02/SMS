"""
Django settings for Theone project.
"""

import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(*candidates: Path) -> None:
    for env_path in candidates:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)
        break


def get_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_list(name: str, default: str = "") -> list[str]:
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def build_sqlite_config(db_name: str) -> dict[str, str]:
    db_path = Path(db_name)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_name
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(db_path),
    }


def database_config() -> dict[str, str]:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        db_engine = os.environ.get("DB_ENGINE", "sqlite").strip().lower()
        if db_engine in {"sqlite", "sqlite3"}:
            db_name = os.environ.get("DB_NAME", "db.sqlite3")
            return build_sqlite_config(db_name)

        engine_map = {
            "postgres": "django.db.backends.postgresql",
            "postgresql": "django.db.backends.postgresql",
            "mysql": "django.db.backends.mysql",
        }
        return {
            "ENGINE": engine_map.get(db_engine, "django.db.backends.postgresql"),
            "NAME": os.environ.get("DB_NAME", ""),
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", ""),
        }

    parsed = urlparse(database_url)
    scheme = parsed.scheme.lower()
    if scheme in {"sqlite", "sqlite3"}:
        sqlite_name = parsed.path.lstrip("/") or "db.sqlite3"
        return build_sqlite_config(sqlite_name)

    engine_map = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "pgsql": "django.db.backends.postgresql",
        "mysql": "django.db.backends.mysql",
    }
    options = {}
    query_params = parse_qs(parsed.query)
    if "sslmode" in query_params:
        options["sslmode"] = query_params["sslmode"][-1]

    config = {
        "ENGINE": engine_map.get(scheme, "django.db.backends.postgresql"),
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }
    if options:
        config["OPTIONS"] = options
    return config


load_env_file(BASE_DIR / ".env", BASE_DIR / "sms.env")


SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-change-me")
DEBUG = get_bool("DEBUG", True)
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
#get_list( "127.0.0.1", "localhost") #"ALLOWED_HOSTS",
CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:8000', 'http://localhost:8000']
# CSRF_TRUSTED_ORIGINS = get_list("CSRF_TRUSTED_ORIGINS", "")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "student",
    'django_extensions',
]

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

ROOT_URLCONF = "Theone.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "Theone.wsgi.application"


DATABASES = {
    "default": database_config(),
}


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
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


if not DEBUG:
    SECURE_SSL_REDIRECT = get_bool("SECURE_SSL_REDIRECT", False) #True
    SESSION_COOKIE_SECURE = get_bool("SESSION_COOKIE_SECURE",False) # True
    CSRF_COOKIE_SECURE = get_bool("CSRF_COOKIE_SECURE",False) # True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # SECURE_REFERRER_POLICY = "same-origin"
    # SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS",0))
    # "31536000"
    SECURE_HSTS_INCLUDE_SUBDOMAINS = get_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS",False)
    # True
    SECURE_HSTS_PRELOAD = get_bool("SECURE_HSTS_PRELOAD", False)
    #True
    X_FRAME_OPTIONS = "DENY"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


SMS_ENABLED = get_bool("SMS_ENABLED", False)
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "twilio").strip().lower()
SMS_DEFAULT_COUNTRY_CODE = os.environ.get("SMS_DEFAULT_COUNTRY_CODE", "+91").strip()
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
