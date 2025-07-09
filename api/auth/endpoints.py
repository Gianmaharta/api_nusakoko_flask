"""Routes for authentication and user profile management"""
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, decode_token, jwt_required, get_jwt_identity
from flask_bcrypt import Bcrypt
import os
import time
from werkzeug.utils import secure_filename
import mysql.connector

# --- PERUBAHAN 1: Ganti sumber koneksi ---
# Hapus import helper lama
# from helper.db_helper import get_connection 
# Gunakan db_pool dari app
from app import db_pool

bcrypt = Bcrypt()
auth_endpoints = Blueprint('auth', __name__)

# --- PERUBAHAN 2: Tambahkan fungsi get_db_connection yang konsisten ---
def get_db_connection():
    """Fungsi helper untuk MEMINJAM koneksi dari pool."""
    try:
        return db_pool.get_connection()
    except Exception as e:
        print(f"Error getting connection from pool: {e}")
        return None

@auth_endpoints.route('/login', methods=['POST'])
def login():
    # ... (Fungsi login Anda sudah benar, tidak perlu diubah) ...
    username = request.form['username']
    password = request.form['password']
    if not username or not password:
        return jsonify({"msg": "Username and password are required"}), 400
    
    # Gunakan fungsi koneksi yang baru dan konsisten
    connection = get_db_connection() 
    cursor = connection.cursor(dictionary=True)
    query = "SELECT * FROM users WHERE username = %s AND deleted_at IS NULL"
    cursor.execute(query, (username,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()

    if not user or not bcrypt.check_password_hash(user.get('password'), password):
        return jsonify({"msg": "Bad username or password"}), 401

    user_id = user.get('id_users')
    role = user.get('role', 'user')
    access_token = create_access_token(
        identity=str(user_id),
        additional_claims={'role': role}
    )
    decoded_token = decode_token(access_token)
    expires = decoded_token['exp']
    return jsonify({
        "access_token": access_token,
        "expires_in": expires,
        "type": "Bearer",
        "role": role,
        "user_id": user_id
    })


@auth_endpoints.route('/register', methods=['POST'])
def register():
    # ... (Fungsi register Anda diubah sedikit untuk menggunakan koneksi baru) ...
    username = request.form['username']
    email = request.form.get('email')
    password = request.form['password']
    address = request.form.get('address')
    if not all([username, email, password]):
        return jsonify({"msg": "Username, email, and password are required"}), 400
        
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    role = "user"
    
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        insert_query = "INSERT INTO users (username, email, password, role, address) VALUES (%s, %s, %s, %s, %s)"
        request_insert = (username, email, hashed_password, role, address)
        cursor.execute(insert_query, request_insert)
        connection.commit()
        new_id = cursor.lastrowid
        return jsonify({"message": "User created successfully", "user_id": new_id}), 201
    except mysql.connector.Error as err:
        if err.errno == 1062:
            return jsonify({"error": "Username atau email sudah terdaftar."}), 409
        return jsonify({"error": f"Failed to register user. {err}"}), 500
    finally:
        cursor.close()
        connection.close()


@auth_endpoints.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    # ... (Fungsi get_profile diubah untuk menggunakan koneksi baru) ...
    current_user_id = get_jwt_identity()
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT id_users, username, email, role, address, profile_photo_url, created_at FROM users WHERE id_users = %s"
        cursor.execute(query, (current_user_id,))
        user = cursor.fetchone()
        if not user: return jsonify({"error": "User profile not found for the provided token"}), 404
        return jsonify(user)
    finally:
        cursor.close()
        conn.close()


@auth_endpoints.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    # ... (Fungsi update_profile diubah untuk menggunakan koneksi baru) ...
    current_user_id = get_jwt_identity()
    form_data = request.form
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        # ... (sisa logika update sama persis seperti kode Anda) ...
        # Cek user
        cursor.execute("SELECT profile_photo_url FROM users WHERE id_users = %s", (current_user_id,))
        user = cursor.fetchone()
        if not user: return jsonify({"error": "User profile not found"}), 404
        # Proses file
        new_image_url = None
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                unique_filename = f"{int(time.time())}_{filename}"
                upload_folder = current_app.config.get('AVATAR_UPLOAD_FOLDER', 'static/uploads/avatars') 
                file_path = os.path.join(upload_folder, unique_filename)
                os.makedirs(upload_folder, exist_ok=True)
                file.save(file_path)
                new_image_url = f"{request.host_url}{file_path}"
        # Proses update dinamis
        fields_to_update, values = [], []
        if 'username' in form_data:
            fields_to_update.append("username = %s")
            values.append(form_data['username'])
        if 'address' in form_data:
            fields_to_update.append("address = %s")
            values.append(form_data['address'])
        if 'email' in form_data:
            fields_to_update.append("email = %s")
            values.append(form_data['email'])
        if new_image_url:
            fields_to_update.append("profile_photo_url = %s")
            values.append(new_image_url)
        if not fields_to_update:
            return jsonify({"message": "No data provided to update"}), 400
        query = f"UPDATE users SET {', '.join(fields_to_update)} WHERE id_users = %s"
        values.append(current_user_id)
        cursor.execute(query, tuple(values))
        conn.commit()
        return jsonify({"message": "Profile updated successfully"})
    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1062:
            return jsonify({"error": "Email atau username ini sudah digunakan oleh akun lain."}), 409
        return jsonify({"error": f"Database error: {err}"}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"An error occurred: {e}"}), 400
    finally:
        cursor.close()
        conn.close()