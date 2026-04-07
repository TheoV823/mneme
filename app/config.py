import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    DB_PATH = os.environ.get("MNEME_DB_PATH", "mneme.db")
    MODEL = os.environ.get("MNEME_MODEL", "claude-sonnet-4-20250514")
    TEMPERATURE = float(os.environ.get("MNEME_TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.environ.get("MNEME_MAX_TOKENS", "2048"))
    PROTOCOL_VERSION = os.environ.get("MNEME_PROTOCOL_VERSION", "v1")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    APP_VERSION = "0.1.0"
