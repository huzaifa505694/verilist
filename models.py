import bcrypt
import jwt
import datetime
import uuid
import json
from backend.db import get_db_connection, get_db_cursor, qp, DB_TYPE

JWT_SECRET = 'super-secret-key-change-this-in-production-12345'
COOKIE_NAME = 'token'

# Auth Helpers
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(10)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def generate_token(user_id: str, email: str, role: str) -> str:
    payload = {
        'userId': user_id,
        'email': email,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def decode_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# User Queries
def get_user_by_email(email: str):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('SELECT * FROM users WHERE LOWER(email) = LOWER(%s)')
    cursor.execute(query, (email,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

def get_user_by_id(user_id: str):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('SELECT * FROM users WHERE id = %s')
    cursor.execute(query, (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

def create_user(email: str, password_hash: str, name: str, role: str) -> dict:
    user_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('INSERT INTO users (id, email, password_hash, name, role) VALUES (%s, %s, %s, %s, %s)')
    cursor.execute(query, (user_id, email.lower(), password_hash, name, role))
    conn.commit()
    
    query_select = qp('SELECT id, email, name, role FROM users WHERE id = %s')
    cursor.execute(query_select, (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user)

def update_user_role(user_id: str, role: str) -> bool:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('UPDATE users SET role = %s WHERE id = %s')
    cursor.execute(query, (role, user_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

# Listing Queries
def create_listing(listing_data: dict) -> dict:
    listing_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('''
        INSERT INTO listings (
            id, title, description, price, make, model, year, mileage, condition, 
            category, status, seller_id, trust_score, predicted_price_min, 
            predicted_price_max, risk_flags
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''')
    cursor.execute(query, (
        listing_id,
        listing_data['title'],
        listing_data['description'],
        listing_data['price'],
        listing_data['make'],
        listing_data['model'],
        listing_data['year'],
        listing_data['mileage'],
        listing_data['condition'],
        listing_data['category'],
        listing_data.get('status', 'ACTIVE'),
        listing_data['seller_id'],
        listing_data.get('trust_score', 100),
        listing_data.get('predicted_price_min'),
        listing_data.get('predicted_price_max'),
        json.dumps(listing_data.get('risk_flags', []))
    ))
    conn.commit()
    
    query_select = qp('SELECT * FROM listings WHERE id = %s')
    cursor.execute(query_select, (listing_id,))
    listing = cursor.fetchone()
    conn.close()
    
    res = dict(listing)
    res['risk_flags'] = json.loads(res['risk_flags']) if res['risk_flags'] else []
    return res

def get_listings(filters: dict = None) -> list:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = 'SELECT l.*, u.name as seller_name, u.email as seller_email FROM listings l JOIN users u ON l.seller_id = u.id WHERE 1=1'
    params = []
    
    if filters:
        if 'status' in filters:
            query += ' AND l.status = %s'
            params.append(filters['status'])
        else:
            query += ' AND l.status = \'ACTIVE\''
            
        if 'category' in filters and filters['category']:
            query += ' AND l.category = %s'
            params.append(filters['category'])
            
        if 'make' in filters and filters['make']:
            query += ' AND LOWER(l.make) = LOWER(%s)'
            params.append(filters['make'])
            
        if 'model' in filters and filters['model']:
            query += ' AND LOWER(l.model) = LOWER(%s)'
            params.append(filters['model'])
            
        if 'year_min' in filters and filters['year_min']:
            query += ' AND l.year >= %s'
            params.append(int(filters['year_min']))
            
        if 'year_max' in filters and filters['year_max']:
            query += ' AND l.year <= %s'
            params.append(int(filters['year_max']))
            
        if 'price_min' in filters and filters['price_min']:
            query += ' AND l.price >= %s'
            params.append(float(filters['price_min']))
            
        if 'price_max' in filters and filters['price_max']:
            query += ' AND l.price <= %s'
            params.append(float(filters['price_max']))
            
        if 'search' in filters and filters['search']:
            query += ' AND (l.title LIKE %s OR l.description LIKE %s)'
            search_param = f"%{filters['search']}%"
            params.append(search_param)
            params.append(search_param)
            
        if 'seller_id' in filters and filters['seller_id']:
            query += ' AND l.seller_id = %s'
            params.append(filters['seller_id'])
    else:
        query += ' AND l.status = \'ACTIVE\''

    query += ' ORDER BY l.created_at DESC'
    
    cursor.execute(qp(query), params)
    rows = cursor.fetchall()
    conn.close()
    
    listings = []
    for r in rows:
        d = dict(r)
        d['risk_flags'] = json.loads(d['risk_flags']) if d['risk_flags'] else []
        listings.append(d)
    return listings

def get_listing_by_id(listing_id: str):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('''
        SELECT l.*, u.name as seller_name, u.email as seller_email 
        FROM listings l 
        JOIN users u ON l.seller_id = u.id 
        WHERE l.id = %s
    ''')
    cursor.execute(query, (listing_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d['risk_flags'] = json.loads(d['risk_flags']) if d['risk_flags'] else []
        return d
    return None

def update_listing_status(listing_id: str, status: str) -> bool:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('UPDATE listings SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s')
    cursor.execute(query, (status, listing_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def update_listing(listing_id: str, update_data: dict) -> bool:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = 'UPDATE listings SET '
    params = []
    
    fields = ['title', 'description', 'price', 'make', 'model', 'year', 'mileage', 'condition', 'category', 'status', 'trust_score', 'predicted_price_min', 'predicted_price_max']
    for f in fields:
        if f in update_data:
            query += f"{f} = %s, "
            params.append(update_data[f])
            
    if 'risk_flags' in update_data:
        query += 'risk_flags = %s, '
        params.append(json.dumps(update_data['risk_flags']))
        
    query += 'updated_at = CURRENT_TIMESTAMP WHERE id = %s'
    params.append(listing_id)
    
    # Clean query format replacing final trailing comma
    query_exec = query.replace(', updated_at', ' updated_at')
    cursor.execute(qp(query_exec), params)
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def delete_listing(listing_id: str) -> bool:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('DELETE FROM listings WHERE id = %s')
    cursor.execute(query, (listing_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

# Saved Listings
def toggle_saved_listing(user_id: str, listing_id: str) -> str:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    
    query_select = qp('SELECT 1 FROM saved_listings WHERE user_id = %s AND listing_id = %s')
    cursor.execute(query_select, (user_id, listing_id))
    existing = cursor.fetchone()
    
    if existing:
        query_delete = qp('DELETE FROM saved_listings WHERE user_id = %s AND listing_id = %s')
        cursor.execute(query_delete, (user_id, listing_id))
        conn.commit()
        status = 'unsaved'
    else:
        query_insert = qp('INSERT INTO saved_listings (user_id, listing_id) VALUES (%s, %s)')
        cursor.execute(query_insert, (user_id, listing_id))
        conn.commit()
        status = 'saved'
    conn.close()
    return status

def get_saved_listings_for_user(user_id: str) -> list:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('''
        SELECT l.*, u.name as seller_name, u.email as seller_email 
        FROM saved_listings sl
        JOIN listings l ON sl.listing_id = l.id
        JOIN users u ON l.seller_id = u.id
        WHERE sl.user_id = %s
        ORDER BY sl.created_at DESC
    ''')
    cursor.execute(query, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    listings = []
    for r in rows:
        d = dict(r)
        d['risk_flags'] = json.loads(d['risk_flags']) if d['risk_flags'] else []
        listings.append(d)
    return listings

# Offers Queries
def create_offer(listing_id: str, buyer_id: str, amount: float) -> dict:
    offer_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('INSERT INTO offers (id, listing_id, buyer_id, amount) VALUES (%s, %s, %s, %s)')
    cursor.execute(query, (offer_id, listing_id, buyer_id, amount))
    conn.commit()
    
    query_select = qp('SELECT * FROM offers WHERE id = %s')
    cursor.execute(query_select, (offer_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)

def get_offers_for_user(user_id: str, role: str) -> list:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    if role == 'SELLER':
        query = qp('''
            SELECT o.*, l.title as listing_title, l.price as listing_price, u.name as buyer_name 
            FROM offers o
            JOIN listings l ON o.listing_id = l.id
            JOIN users u ON o.buyer_id = u.id
            WHERE l.seller_id = %s
            ORDER BY o.created_at DESC
        ''')
    else:
        query = qp('''
            SELECT o.*, l.title as listing_title, l.price as listing_price, u.name as seller_name 
            FROM offers o
            JOIN listings l ON o.listing_id = l.id
            JOIN users u ON l.seller_id = u.id
            WHERE o.buyer_id = %s
            ORDER BY o.created_at DESC
        ''')
    cursor.execute(query, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_offer_status(offer_id: str, status: str) -> bool:
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    query = qp('UPDATE offers SET status = %s WHERE id = %s')
    cursor.execute(query, (status, offer_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0
