"""Static endpoint to show image"""
from flask import Blueprint, send_from_directory

static_file_server = Blueprint('static_file_server', __name__)

# Untuk serve gambar produk
@static_file_server.route('uploads/products/<path:filename>')
def serve_product_image(filename):
    return send_from_directory('static/uploads/products', filename)

# (Opsional) Untuk serve avatar user
@static_file_server.route('uploads/avatars/<path:filename>')
def serve_avatar_image(filename):
    return send_from_directory('static/uploads/avatars', filename)
