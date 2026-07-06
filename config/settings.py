from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    SECRET_KEY = "meditrack-demo-secret"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'database' / 'meditrack.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
