import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

try:
    # Use ThreadedConnectionPool for Flask
    db_pool = psycopg2.pool.ThreadedConnectionPool(1, 20, dsn=DATABASE_URL)
    if db_pool:
        print("Connection pool created successfully")
except (Exception, psycopg2.DatabaseError) as error:
    print("Error while connecting to PostgreSQL:", error)
    db_pool = None

def get_connection():
    if not db_pool:
        return None
    try:
        connection = db_pool.getconn()
        return connection
    except Exception as e:
        print(f"Error getting connection from pool: {e}")
        return None

def release_connection(connection):
    if not db_pool or not connection:
        return
    try:
        db_pool.putconn(connection)
    except Exception as e:
        print(f"Error releasing connection: {e}")

def initialize_database():
    """Initialize the database schema if it doesn't already exist"""
    if not db_pool:
        print("Warning: Database pool not initialized, skipping schema setup")
        return
    
    try:
        schema_file = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'schema.sql')
        
        if not os.path.exists(schema_file):
            print(f"Warning: Schema file not found at {schema_file}")
            return
        
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        conn = get_connection()
        if not conn:
            print("Error: Could not get database connection for initialization")
            return
        
        try:
            with conn.cursor() as cursor:
                cursor.execute(schema_sql)
            conn.commit()
            print("Database schema initialized successfully")
        except Exception as e:
            conn.rollback()
            print(f"Error initializing database schema: {e}")
        finally:
            release_connection(conn)
    except Exception as e:
        print(f"Error in initialize_database: {e}")
