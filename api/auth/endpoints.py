"""Routes for module books"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, decode_token
from flask_bcrypt import Bcrypt

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
    request_query = (username,)
    cursor.execute(query, request_query)
    user = cursor.fetchone()
    cursor.close()

    if not user or not bcrypt.check_password_hash(user.get('password'), password):
        return jsonify({"msg": "Bad username or password"}), 401

    role = user.get('role', 'user')  # default ke 'user' jika tidak ada
    access_token = create_access_token(
        identity=str({'username': username, 'role': role}),
        additional_claims={'roles': role}
    )
    decoded_token = decode_token(access_token)
    expires = decoded_token['exp']
    return jsonify({
        "access_token": access_token,
        "expires_in": expires,
        "type": "Bearer",
        "role": role
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
