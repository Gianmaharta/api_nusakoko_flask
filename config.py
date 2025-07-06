"""Store the config"""
from datetime import timedelta
import os
import dataclasses
from dotenv import load_dotenv

load_dotenv()

@dataclasses.dataclass
class Config:
    """Load the configuration key SECRET and JWT_SECRET """
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'supersecretjwtkey')
    JWT_ACCESS_TOKEN_EXPIRES = os.getenv(
        'JWT_ACCESS_TOKEN_EXPIRES', timedelta(seconds=int(3600)))
    
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DB = os.getenv('MYSQL_DB', 'nusakoko')

    UPLOAD_FOLDER = 'static/uploads/products'

    AVATAR_UPLOAD_FOLDER = 'static/uploads/avatars'
