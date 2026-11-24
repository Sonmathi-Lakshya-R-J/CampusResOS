import os
import mysql.connector
from mysql.connector import pooling

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="campusresos_pool",
            pool_size=10,
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "campusresos"),
            user=os.getenv("DB_USER", "campusresos_app"),
            password=os.getenv("DB_PASSWORD", ""),
            autocommit=False,
        )
    return _pool

def get_connection():
    return get_pool().get_connection()
