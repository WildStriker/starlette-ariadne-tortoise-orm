"""configuration settings"""
from starlette.config import Config
from starlette.datastructures import Secret

# Config will be read from environment variables and/or ".env" files.
CONFIG = Config(".env")

DEBUG = CONFIG('DEBUG', cast=bool, default=False)
DATABASE_URL = CONFIG('DATABASE_URL')
JWT_SECRET_KEY = CONFIG('JWT_SECRET_KEY', cast=Secret)
