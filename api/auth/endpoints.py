"""Routes for module books"""
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, decode_token, jwt_required, get_jwt_identity
from flask_bcrypt import Bcrypt
import os
import time
from werkzeug.utils import secure_filename

from helper.db_helper import get_connection

bcrypt = Bcrypt()
auth_endpoints = Blueprint('auth', __name__)


@auth_endpoints.route('/login', methods=['POST'])
def login():
    """Routes for authentication"""
    username = request.form['username']
    password = request.form['password']

    if not username or not password:
        return jsonify({"msg": "Username and password are required"}), 400

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    query = "SELECT * FROM users WHERE username = %s AND deleted_at IS NULL"
    cursor.execute(query, (username,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()

    if not user or not bcrypt.check_password_hash(user.get('password'), password):
        return jsonify({"msg": "Bad username or password"}), 401

    # --- PERUBAHAN UTAMA DI SINI ---
    # 1. Ambil id_users dari data user
    user_id = user.get('id_users')
    role = user.get('role', 'user')
    
    # 2. Gunakan user_id (angka) sebagai identity, BUKAN string
    access_token = create_access_token(
        identity=str(user_id),
        additional_claims={'role': role}
    )
    # ---------------------------------
    
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
    """Routes for register"""
    username = request.form['username']
    email = request.form['email'] if 'email' in request.form else None
    if not username or not email:
        return jsonify({"msg": "Username and email are required"}), 400
    password = request.form['password']
    # To hash a password
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    role = "user"
    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO users (username, email, password, role) values (%s, %s, %s, %s)"
    request_insert = (username, email, hashed_password, role)
    cursor.execute(insert_query, request_insert)
    connection.commit()
    cursor.close()
    new_id = cursor.lastrowid
    if new_id:
        return jsonify({"message": "OK",
                        "description": "User created",
                        "username": username}), 201
    return jsonify({"message": "Failed, cant register user"}), 501

# ENDPOINT BARU UNTUK UPDATE PROFIL
@auth_endpoints.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Endpoint untuk user mengupdate profil (alamat, foto, dll)."""
    
    current_user_id = get_jwt_identity()
    print(f"DEBUG: ID dari token JWT adalah: {current_user_id}, Tipe datanya: {type(current_user_id)}")
    form_data = request.form
    
    conn = get_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor(dictionary=True)

    try:
        # --- Bagian Logika Update Foto (Opsional) ---
        new_image_url = None

        # TAMBAHKAN VALIDASI INI: Cek apakah user benar-benar ditemukan
        cursor.execute("SELECT profile_photo_url FROM users WHERE id_users = %s", (current_user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "User profile not found for the provided token"}), 404

        # Jika ada file baru, proses dan simpan
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename != '':
                old_image_url = user.get('profile_photo_url')
                # ... (Logika menyimpan file baru dan menghapus file lama) ...
                # ... (Sama seperti kode di respons sebelumnya) ...
                filename = secure_filename(file.filename)
                unique_filename = f"{int(time.time())}_{filename}"
                upload_folder = current_app.config.get('AVATAR_UPLOAD_FOLDER', 'static/uploads/avatars') 
                file_path = os.path.join(upload_folder, unique_filename)
                os.makedirs(upload_folder, exist_ok=True)
                file.save(file_path)
                new_image_url = f"{request.host_url}{file_path}"
        
        # --- Bagian Logika Update Data Teks (Dinamis) ---
        fields_to_update = []
        values = []

        if 'username' in form_data:
            fields_to_update.append("username = %s")
            values.append(form_data['username'])
        if 'address' in form_data:
            fields_to_update.append("address = %s")
            values.append(form_data['address'])
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

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()