"""Small apps to demonstrate endpoints with basic feature - CRUD"""

# 1. Impor library utama
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from extensions import jwt
from config import Config
from static.static_file_server import static_file_server
from flasgger import Swagger
import mysql.connector.pooling

# Load environment variables
load_dotenv()

# 2. Inisialisasi Aplikasi Flask
app = Flask(__name__)
app.config.from_object(Config)
CORS(app, origins=["http://localhost:5173"], supports_credentials=True)
Swagger(app)
jwt.init_app(app)

# 3. Buat Koneksi Pool
try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="nusakoko_pool",
        pool_size=5,
        pool_reset_session=True,
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    print("Database connection pool created successfully.")
except mysql.connector.Error as err:
    print(f"Error creating connection pool: {err}")
    db_pool = None

# 4. PENTING: Impor Blueprint DI SINI, SETELAH db_pool DIBUAT
from api.auth.endpoints import auth_endpoints
from api.products.endpoints import products_blueprint
from api.orders.endpoints import orders_blueprint
# from api.books.endpoints import books_endpoints # Hapus atau aktifkan jika perlu
# from api.data_protected.endpoints import protected_endpoints # Hapus atau aktifkan jika perlu


# 5. Daftarkan (Register) Blueprint
app.register_blueprint(auth_endpoints, url_prefix='/api/nusakoko/auth')
app.register_blueprint(products_blueprint, url_prefix='/api/nusakoko/products')
app.register_blueprint(orders_blueprint, url_prefix='/api/nusakoko/orders')
app.register_blueprint(static_file_server, url_prefix='/static/')


# 6. Jalankan Aplikasi
if __name__ == '__main__':
    app.run(debug=True)