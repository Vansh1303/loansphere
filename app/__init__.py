from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from app.db.db import initialize_database
from app.config import JWT_SECRET_KEY, UPLOAD_FOLDER, GENERATED_FOLDER
import os

def create_app():
    # Initialize database first
    initialize_database()
    
    app = Flask(__name__,
        static_folder=os.path.abspath('static'),
        static_url_path='/static')
    CORS(app)
    
    # Configure JWT
    app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
    jwt = JWTManager(app)
    
    # Ensure upload/generated directories exist
    upload_folder = UPLOAD_FOLDER or 'static/uploads'
    generated_folder = GENERATED_FOLDER or 'static/generated'
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(generated_folder, exist_ok=True)
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.generate import generate_bp
    from app.routes.summarize import summarize_bp
    from app.routes.extract import extract_bp
    from app.routes.chat import chat_bp
    from app.routes.index import index_bp
    from app.routes.kyc import kyc_bp
    from app.routes.financial_profile import financial_profile_bp
    from app.routes.credit_score import credit_score_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(generate_bp, url_prefix='/api')
    app.register_blueprint(summarize_bp, url_prefix='/api')
    app.register_blueprint(extract_bp, url_prefix='/api')
    app.register_blueprint(chat_bp, url_prefix='/api')
    app.register_blueprint(index_bp)
    app.register_blueprint(kyc_bp, url_prefix='/api/kyc')
    app.register_blueprint(financial_profile_bp, url_prefix='/api')
    app.register_blueprint(credit_score_bp, url_prefix='/api')
    
    return app
