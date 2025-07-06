from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import mysql.connector
from app import db_pool

cart_blueprint = Blueprint('cart', __name__)

def get_db_connection():
    return db_pool.get_connection()

@cart_blueprint.route('/', methods=['GET'])
@jwt_required()
def get_cart_items():
    """Mengambil semua item di keranjang user yang sedang login."""
    user_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT c.product_id as id, p.name, p.price, c.quantity, p.stock_quantity as stock, p.image_url
            FROM cart_items c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        """
        cursor.execute(query, (user_id,))
        cart_items = cursor.fetchall()
        return jsonify(cart_items)
    finally:
        cursor.close()
        conn.close()

@cart_blueprint.route('/add', methods=['POST'])
@jwt_required()
def add_to_cart():
    """Menambah item ke keranjang atau mengupdate quantity jika sudah ada."""
    user_id = get_jwt_identity()
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Query ini akan menambah item, atau jika sudah ada, akan menambah quantity-nya
        query = """
            INSERT INTO cart_items (user_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
        """
        cursor.execute(query, (user_id, product_id, quantity))
        conn.commit()
        return jsonify({"message": "Item added to cart successfully"}), 201
    finally:
        cursor.close()
        conn.close()

@cart_blueprint.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update_cart_item(product_id):
    """Mengubah quantity item di keranjang."""
    user_id = get_jwt_identity()
    data = request.get_json()
    quantity = data.get('quantity')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "UPDATE cart_items SET quantity = %s WHERE user_id = %s AND product_id = %s"
        cursor.execute(query, (quantity, user_id, product_id))
        conn.commit()
        return jsonify({"message": "Cart item updated"})
    finally:
        cursor.close()
        conn.close()

@cart_blueprint.route('/remove/<product_id>', methods=['DELETE'])
@jwt_required()
def remove_from_cart(product_id):
    """Menghapus item dari keranjang."""
    user_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "DELETE FROM cart_items WHERE user_id = %s AND product_id = %s"
        cursor.execute(query, (user_id, product_id))
        conn.commit()
        return jsonify({"message": "Item removed from cart"})
    finally:
        cursor.close()
        conn.close()