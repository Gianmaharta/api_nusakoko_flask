# backend/api/products/endpoints.py

from flask import Blueprint, jsonify, current_app, request
import mysql.connector
import os
import time
from werkzeug.utils import secure_filename
from app import db_pool

# Ganti nama blueprint agar spesifik
products_blueprint = Blueprint('products', __name__)

def get_db_connection():
    """Fungsi helper untuk MEMINJAM koneksi dari pool."""
    try:
        return db_pool.get_connection()
    except Exception as e:
        print(f"Error getting connection from pool: {e}")
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
    """Endpoint untuk menambah produk baru dengan upload gambar."""
    
    # 1. Cek apakah ada file yang dikirim
    if 'product_image' not in request.files:
        return jsonify({"error": "No image file part"}), 400
    
    file = request.files['product_image']
    
    # 2. Cek apakah nama file tidak kosong
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()
    
    try:
        # 3. Proses dan simpan file gambar
        if file:
            # Mengamankan nama file dari karakter berbahaya
            filename = secure_filename(file.filename)
            # Membuat nama file unik dengan timestamp untuk menghindari duplikat
            unique_filename = f"{int(time.time())}_{filename}"
            # Path lengkap untuk menyimpan file
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # 4. Membuat URL yang bisa diakses dari frontend
            # request.host_url akan menghasilkan sesuatu seperti 'http://127.0.0.1:5000/'
            image_url = f"{request.host_url}{file_path}"
        
        # 5. Ambil data lain dari form dan simpan ke database
        data = request.form
        query = """
            INSERT INTO products (name, sku, description, price, stock_quantity, coir_weight_grams, image_url, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            data['name'], data['sku'], data['description'], data['price'],
            data['stock_quantity'], data.get('coir_weight_grams', 10), 
            image_url, # Gunakan URL yang sudah kita buat
            data.get('is_active', 1)
        )
        cursor.execute(query, values)
        conn.commit()
        return jsonify({"message": "Product created successfully", "image_url": image_url}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@products_blueprint.route('/<product_id>', methods=['PUT'])
def update_product(product_id):
    """Endpoint untuk update produk, termasuk gambar (opsional)."""
    
    data = request.form
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Ambil URL gambar yang sekarang ada di database
        cursor.execute("SELECT image_url FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        current_image_url = product['image_url']

        # 2. Cek apakah ada file gambar baru yang dikirim
        if 'product_image' in request.files:
            file = request.files['product_image']
            # Pastikan file benar-benar dipilih
            if file and file.filename != '':
                # Proses dan simpan file gambar baru
                filename = secure_filename(file.filename)
                unique_filename = f"{int(time.time())}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                
                # Buat URL baru untuk disimpan ke database
                current_image_url = f"{request.host_url}{file_path}"
                
                # (Opsional tapi bagus) Hapus file gambar lama untuk menghemat ruang
                # Kode ini perlu penyesuaian path jika server production berbeda
                old_image_path_part = product['image_url'].split('/')[-3:]
                old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], '..', *old_image_path_part)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)

        # 3. Siapkan query UPDATE
        query = """
            UPDATE products SET name=%s, sku=%s, description=%s, price=%s, stock_quantity=%s,
            coir_weight_grams=%s, image_url=%s, is_active=%s WHERE id=%s
        """
        values = (
            data.get('name'), data.get('sku'), data.get('description'),
            data.get('price'), data.get('stock_quantity'),
            data.get('coir_weight_grams', 10),
            current_image_url, # Gunakan URL baru jika ada, atau URL lama jika tidak
            data.get('is_active', 1),
            product_id
        )
        
        cursor.execute(query, values)
        conn.commit()
        return jsonify({"message": "Product updated successfully", "image_url": current_image_url})

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