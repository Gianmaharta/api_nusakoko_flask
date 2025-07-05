# backend/api/products/endpoints.py

from flask import Blueprint, jsonify, current_app, request
import mysql.connector

# Ganti nama blueprint agar spesifik
products_blueprint = Blueprint('products', __name__)

def get_db_connection():
    """Fungsi helper untuk membuat koneksi ke database dari config."""
    try:
        conn = mysql.connector.connect(
            host=current_app.config['MYSQL_HOST'],
            user=current_app.config['MYSQL_USER'],
            password=current_app.config['MYSQL_PASSWORD'],
            database=current_app.config['MYSQL_DB']
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

@products_blueprint.route('/', methods=['GET'])
def get_products():
    """Endpoint untuk mengambil semua data produk."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT id, name, sku, description, price, stock_quantity, coir_weight_grams, image_url, is_active FROM products WHERE is_active = TRUE"
        cursor.execute(query)
        products = cursor.fetchall()
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify(products)

@products_blueprint.route('/', methods=['POST'])
def create_product():
    """Endpoint untuk menambah produk baru."""
    data = request.form
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO products (name, sku, description, price, stock_quantity, coir_weight_grams, image_url, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            data['name'], data['sku'], data['description'], data['price'],
            data['stock_quantity'], data.get('coir_weight_grams', 10), data['image_url'], data.get('is_active', 1)
        )
        cursor.execute(query, values)
        conn.commit()
        return jsonify({"message": "Product created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@products_blueprint.route('/<product_id>', methods=['PUT'])
def update_product(product_id):
    """Endpoint untuk update produk."""
    data = request.form
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            UPDATE products SET name=%s, sku=%s, description=%s, price=%s, stock_quantity=%s,
            coir_weight_grams=%s, image_url=%s, is_active=%s WHERE id=%s
        """
        values = (
            data.get('name'),
            data.get('sku'),
            data.get('description'),
            data.get('price'),
            data.get('stock_quantity'),
            data.get('coir_weight_grams', 10),
            data.get('image_url'),
            data.get('is_active', 1),
            product_id
        )
        cursor.execute(query, values)
        conn.commit()
        return jsonify({"message": "Product updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@products_blueprint.route('/<product_id>', methods=['DELETE'])
def soft_delete_product(product_id):
    """Endpoint untuk soft delete produk."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "UPDATE products SET is_active=0 WHERE id=%s"
        cursor.execute(query, (product_id,))
        conn.commit()
        return jsonify({"message": "Product soft deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()