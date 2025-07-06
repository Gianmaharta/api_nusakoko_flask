from flask import Blueprint, jsonify, current_app, request
import mysql.connector
import json
import random
from app import db_pool

# Buat blueprint baru untuk orders
orders_blueprint = Blueprint('orders', __name__)

def get_db_connection():
    """Fungsi helper untuk MEMINJAM koneksi dari pool."""
    try:
        return db_pool.get_connection()
    except Exception as e:
        print(f"Error getting connection from pool: {e}")
        return None

# == READ (GET) ==
@orders_blueprint.route('/', methods=['GET'])
def get_orders():
    """
    Endpoint untuk mengambil semua data pesanan.
    Menggabungkan data dari tabel orders, users, dan products.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Query ini menggunakan JOIN untuk mengambil nama pelanggan
        # dan GROUP_CONCAT untuk menggabungkan semua nama produk dalam satu pesanan
        query = """
            SELECT
                o.id,
                o.order_number,
                o.created_at AS tanggal,
                u.username AS pelanggan,
                o.total_amount AS total_bayar,
                o.payment_status,
                o.order_status,
                o.tracking_number,
                GROUP_CONCAT(p.name SEPARATOR ', ') AS produk
            FROM orders AS o
            JOIN users AS u ON o.user_id = u.id_users
            LEFT JOIN order_items AS oi ON o.id = oi.order_id
            LEFT JOIN products AS p ON oi.product_id = p.id
            GROUP BY o.id
            ORDER BY o.created_at DESC;
        """
        cursor.execute(query)
        orders = cursor.fetchall()

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify(orders)

@orders_blueprint.route('/<order_id>', methods=['GET'])
def get_order_details(order_id):
    """Endpoint untuk mengambil detail satu pesanan beserta item-itemnya."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    order_details = {}

    try:
        # Ambil data pesanan utama
        cursor.execute("SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id_users WHERE o.id = %s", (order_id,))
        order_details = cursor.fetchone()

        if not order_details:
            return jsonify({"error": "Order not found"}), 404

        # Ambil item-item produk dalam pesanan tersebut
        cursor.execute("""
            SELECT p.name, oi.quantity, oi.price_per_item 
            FROM order_items oi 
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """, (order_id,))
        order_details['items'] = cursor.fetchall()

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify(order_details)

# == CREATE (POST) ==
# Catatan: Endpoint ini disederhanakan. Idealnya menggunakan transaksi database.
@orders_blueprint.route('/', methods=['POST'])
def create_order():
    """Endpoint untuk membuat pesanan baru (alamat diambil otomatis dari user)."""
    form_data = request.form
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor(dictionary=True)

    try:
        conn.start_transaction()

        # Ambil user_id dari form
        user_id = form_data.get('user_id')
        if not user_id:
            raise ValueError("`user_id` is required.")

        # 1. Ambil alamat user dari database berdasarkan user_id
        cursor.execute("SELECT address FROM users WHERE id_users = %s", (user_id,))
        user_data = cursor.fetchone()
        
        # 2. Lakukan validasi
        if not user_data:
            raise ValueError(f"User dengan id {user_id} tidak ditemukan.")
        if not user_data['address']:
            raise ValueError("Alamat pengiriman belum diatur di profil user. Silakan lengkapi profil terlebih dahulu.")
        
        # 3. Simpan alamat yang valid untuk digunakan nanti
        shipping_address_from_db = user_data['address']

        # 4. Proses item-item dari 'items_json'
        items_json_string = form_data.get('items_json')
        if not items_json_string: raise ValueError("`items_json` is required.")
        items = json.loads(items_json_string)
        
        total_amount = 0
        order_items_to_insert = []

        # Loop untuk validasi stok, harga, dan pengurangan stok (logika ini tetap sama)
        for item in items:
            product_id = item['product_id']
            quantity_ordered = item['quantity']
            cursor.execute("SELECT price, stock_quantity FROM products WHERE id = %s FOR UPDATE", (product_id,))
            product = cursor.fetchone()
            if not product: raise ValueError(f"Produk dengan id {product_id} tidak ditemukan.")
            if product['stock_quantity'] < quantity_ordered: raise ValueError(f"Stok untuk produk id {product_id} tidak mencukupi.")
            price_per_item = product['price']
            total_amount += (price_per_item * quantity_ordered)
            order_items_to_insert.append((product_id, quantity_ordered, price_per_item))
            new_stock = product['stock_quantity'] - quantity_ordered
            cursor.execute("UPDATE products SET stock_quantity = %s WHERE id = %s", (new_stock, product_id))

        # 5. Insert ke tabel orders menggunakan alamat dari database
        order_query = "INSERT INTO orders (user_id, order_number, total_amount, shipping_address) VALUES (%s, %s, %s, %s)"
        import time
        order_number = f"NKK-{int(time.time())}"
        cursor.execute(order_query, (user_id, order_number, total_amount, shipping_address_from_db))
        order_id = cursor.lastrowid

        # 6. Insert ke tabel order_items (logika ini tetap sama)
        item_query = "INSERT INTO order_items (order_id, product_id, quantity, price_per_item) VALUES (%s, %s, %s, %s)"
        items_with_order_id = [(order_id, *item_data) for item_data in order_items_to_insert]
        cursor.executemany(item_query, items_with_order_id)
        
        conn.commit()

        return jsonify({"message": "Order created successfully", "order_id": order_id}), 201

    except (mysql.connector.Error, ValueError, KeyError, json.JSONDecodeError) as err:
        conn.rollback()
        return jsonify({"error": str(err)}), 400
    finally:
        cursor.close()
        conn.close()

# Endpoint baru khusus untuk konfirmasi pembayaran
@orders_blueprint.route('/<order_id>/confirm-payment', methods=['POST'])
def confirm_order_payment(order_id):
    """
    Endpoint untuk mengkonfirmasi pembayaran.
    Aksi ini akan otomatis mengubah status pembayaran menjadi 'paid',
    mengisi kurir, dan membuat nomor resi acak.
    """
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()

    try:
        # 1. Generate nomor resi acak sesuai format
        random_digits = random.randint(10000000, 99999999)
        tracking_number = f"JN{random_digits}"
        shipping_courier = "JNE"

        # 2. Siapkan query untuk update beberapa kolom sekaligus
        query = """
            UPDATE orders 
            SET 
                payment_status = 'paid', 
                order_status = 'processing', -- Langsung ubah status pesanan juga
                shipping_courier = %s, 
                tracking_number = %s 
            WHERE id = %s
        """
        
        # 3. Eksekusi query
        cursor.execute(query, (shipping_courier, tracking_number, order_id))
        conn.commit()

        # Cek apakah ada baris yang ter-update
        if cursor.rowcount == 0:
            return jsonify({"error": "Order not found"}), 404

        return jsonify({
            "message": f"Payment for order {order_id} confirmed.",
            "shipping_courier": shipping_courier,
            "tracking_number": tracking_number
        })

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# # == UPDATE (PUT/PATCH) ==
# @orders_blueprint.route('/<order_id>/status', methods=['PUT'])
# def update_order_status(order_id):
#     """Endpoint untuk mengubah status pesanan (processing, shipped, etc)."""
    
#     # Ubah baris ini dari request.get_json() menjadi request.form
#     data = request.form 
#     new_status = data.get('status') # e.g., "processing"

#     # Pastikan status yang dikirim valid
#     valid_statuses = ['new', 'processing', 'shipped', 'completed', 'cancelled']
#     if not new_status or new_status not in valid_statuses:
#         return jsonify({"error": "Status is required and must be valid"}), 400

#     conn = get_db_connection()
#     if conn is None: return jsonify({"error": "DB connection failed"}), 500
#     cursor = conn.cursor()
    
#     try:
#         query = "UPDATE orders SET order_status = %s WHERE id = %s"
#         cursor.execute(query, (new_status, order_id))
#         conn.commit()
        
#         if cursor.rowcount == 0:
#             return jsonify({"error": "Order not found"}), 404
        
#         return jsonify({"message": f"Order {order_id} status updated to {new_status}"})
#     except mysql.connector.Error as err:
#         return jsonify({"error": str(err)}), 500
#     finally:
#         cursor.close()
#         conn.close()

# FUNGSI UNTUK TOMBOL "DIPROSES"
@orders_blueprint.route('/<order_id>/process', methods=['POST'])
def process_order(order_id):
    """Endpoint untuk mengubah status menjadi 'processing'."""
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()
    try:
        query = "UPDATE orders SET order_status = 'processing' WHERE id = %s"
        cursor.execute(query, (order_id,))
        conn.commit()
        if cursor.rowcount == 0: return jsonify({"error": "Order not found"}), 404
        return jsonify({"message": f"Order {order_id} has been marked as processing."})
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# Endpoint baru khusus untuk menandai pesanan telah dikirim
@orders_blueprint.route('/<order_id>/ship', methods=['POST'])
def ship_order(order_id):
    """
    Endpoint untuk menandai pesanan sebagai 'shipped'.
    Ini adalah langkah setelah 'processing'.
    """
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()

    try:
        # Cek dulu apakah pesanan memang ada dan statusnya 'processing'
        # Ini opsional tapi merupakan praktik yang baik
        check_cursor = conn.cursor(dictionary=True)
        check_cursor.execute("SELECT order_status FROM orders WHERE id = %s", (order_id,))
        order = check_cursor.fetchone()
        check_cursor.close()

        if not order:
            return jsonify({"error": "Order not found"}), 404
        # if order['order_status'] != 'processing':
        #     return jsonify({"error": f"Order status is currently '{order['order_status']}', not 'processing'"}), 400


        # Query utama untuk update status
        query = "UPDATE orders SET order_status = 'shipped' WHERE id = %s"
        cursor.execute(query, (order_id,))
        conn.commit()

        return jsonify({"message": f"Order {order_id} has been marked as shipped."})

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# == DELETE (Soft Delete) ==
@orders_blueprint.route('/<order_id>', methods=['DELETE'])
def cancel_order(order_id):
    """Endpoint untuk membatalkan pesanan (soft delete)."""
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()

    try:
        # Kita tidak menghapus data, hanya mengubah statusnya menjadi 'cancelled'
        query = "UPDATE orders SET order_status = 'cancelled' WHERE id = %s"
        cursor.execute(query, (order_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Order not found"}), 404

        return jsonify({"message": f"Order {order_id} has been cancelled."})
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()