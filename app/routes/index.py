import os
from flask import Blueprint, send_from_directory

index_bp = Blueprint('index', __name__)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'frontend'))


def serve_frontend(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@index_bp.route('/')
def index():
    return serve_frontend('index.html')


@index_bp.route('/generator')
def generator():
    return serve_frontend('generator.html')


@index_bp.route('/summarizer')
def summarizer():
    return serve_frontend('summarizer.html')


@index_bp.route('/extractor')
def extractor():
    return serve_frontend('extractor.html')


@index_bp.route('/chatbot')
def chatbot():
    return serve_frontend('chatbot.html')


@index_bp.route('/index')
def index_alias():
    return serve_frontend('index.html')


@index_bp.route('/login')
def login():
    return serve_frontend('login.html')


@index_bp.route('/register')
def register():
    return serve_frontend('register.html')

@index_bp.route('/kyc')
def kyc():
    return serve_frontend('kyc.html')


@index_bp.route('/financial-profile')
def financial_profile():
    return serve_frontend('financial-profile.html')


@index_bp.route('/credit-score')
def credit_score():
    return serve_frontend('credit-score.html')


@index_bp.route('/loan-advisor')
def loan_advisor():
    return serve_frontend('loan-advisor.html')

