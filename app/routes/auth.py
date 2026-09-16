from flask import Blueprint, request, jsonify
# pyrefly: ignore [missing-import]
import bcrypt
from flask_jwt_extended import create_access_token
from app.db.db import get_connection, release_connection
import psycopg2

auth_bp = Blueprint('auth', __name__)

# Register route
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password') or not data.get('full_name'):
        return jsonify({"msg": "Missing required fields: email, password, full_name"}), 400
    
    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name')
    
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    conn = get_connection()
    if not conn:
        return jsonify({"msg": "Database connection error"}), 500
        
    try:
        with conn.cursor() as cursor:
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return jsonify({"msg": "Email already registered"}), 409
            
            # Insert new user
            cursor.execute(
                "INSERT INTO users (email, password_hash, full_name) VALUES (%s, %s, %s) RETURNING id",
                (email, hashed_password, full_name)
            )
            user_id = cursor.fetchone()[0]
            conn.commit()
            
        return jsonify({"msg": "User registered successfully", "user_id": user_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"msg": str(e)}), 500
    finally:
        release_connection(conn)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"msg": "Missing email or password"}), 400
        
    email = data.get('email')
    password = data.get('password')
    
    conn = get_connection()
    if not conn:
        return jsonify({"msg": "Database connection error"}), 500
        
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, password_hash, full_name FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if not user:
                return jsonify({"msg": "Invalid credentials"}), 401
                
            user_id, password_hash, full_name = user
            
            if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                access_token = create_access_token(identity=str(user_id))
                return jsonify({
                    "access_token": access_token,
                    "user": {
                        "id": user_id,
                        "email": email,
                        "full_name": full_name
                    }
                }), 200
            else:
                return jsonify({"msg": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"msg": str(e)}), 500
    finally:
        release_connection(conn)
