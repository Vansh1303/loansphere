import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

DATABASE_URL = os.getenv('DATABASE_URL', '')
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'fallback-secret')
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'static' / 'uploads'))
GENERATED_FOLDER = os.getenv('GENERATED_FOLDER', str(BASE_DIR / 'static' / 'generated'))
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY', '')
FLASK_ENV = os.getenv('FLASK_ENV', 'production')

# Setu API configuration
SETU_CLIENT_ID = os.getenv('SETU_CLIENT_ID', '')
SETU_CLIENT_SECRET = os.getenv('SETU_CLIENT_SECRET', '')
SETU_PAN_SCHEME_ID = os.getenv('SETU_PAN_SCHEME_ID', '')
SETU_BANK_SCHEME_ID = os.getenv('SETU_BANK_SCHEME_ID', '')
SETU_BASE_URL = os.getenv('SETU_BASE_URL', 'https://dg-sandbox.setu.co')
