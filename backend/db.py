import os
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'file:./dev.db')

# Detect Database Type
if DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://'):
    DB_TYPE = 'postgres'
else:
    DB_TYPE = 'sqlite'

SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'verilist.db')

def get_db_connection():
    if DB_TYPE == 'postgres':
        # Connect to PostgreSQL
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        # Connect to SQLite
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

def get_db_cursor(conn):
    if DB_TYPE == 'postgres':
        return conn.cursor(cursor_factory=DictCursor)
    else:
        return conn.cursor()

def qp(query):
    """
    Translates SQL query placeholders between Postgres (%s) and SQLite (?) dialects.
    All source queries should be written with %s placeholders.
    """
    if DB_TYPE == 'sqlite':
        return query.replace('%s', '?')
    return query

def init_db():
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'BUYER',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    
    # Create listings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS listings (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        price REAL NOT NULL,
        make TEXT NOT NULL,
        model TEXT NOT NULL,
        year INTEGER NOT NULL,
        mileage INTEGER NOT NULL,
        condition TEXT NOT NULL,
        category TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        seller_id TEXT NOT NULL,
        trust_score INTEGER DEFAULT 100,
        predicted_price_min REAL,
        predicted_price_max REAL,
        risk_flags TEXT, -- JSON string representing array of strings
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE
    );
    ''')
    
    # Create saved_listings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS saved_listings (
        user_id TEXT NOT NULL,
        listing_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, listing_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
    );
    ''')
    
    # Create offers table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS offers (
        id TEXT PRIMARY KEY,
        listing_id TEXT NOT NULL,
        buyer_id TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE
    );
    ''')
    
    # Create reviews table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id TEXT PRIMARY KEY,
        listing_id TEXT,
        reviewer_id TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE SET NULL
    );
    ''')
    
    # Create notifications table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    ''')
    
    # Indexes for performance (required by Week 2)
    # Adding indexes if not exists is different in Postgres vs SQLite.
    # In SQLite/Postgres: CREATE INDEX IF NOT EXISTS works in both.
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_listings_seller ON listings(seller_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_listings_created ON listings(created_at);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviews_seller ON reviews(seller_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON reviews(reviewer_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(user_id, is_read);')
    
    conn.commit()
    conn.close()
    print(f"Database initialized successfully ({DB_TYPE} mode).")

if __name__ == '__main__':
    init_db()
