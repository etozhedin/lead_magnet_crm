import os

os.environ.setdefault("DEBUG", "1")
os.environ.setdefault("DB_ENGINE", "sqlite")
from .settings import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "admin.localhost", "forms.localhost", "testserver"]
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405
