import os
import random
import json
import uuid
from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
from functools import wraps
from dotenv import load_dotenv

# Google OAuth
try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

import backend.models as models
from backend.ai_models.detector import analyze_listing
from backend.ai_models.estimator import PriceEstimator

# Initialize Flask app, pointing the static folder to the frontend directory
app = Flask(__name__, static_folder='../frontend', static_url_path='')

# Configure CORS to allow credentials (cookies)
CORS(app, supports_credentials=True, origins=['http://localhost:5000', 'http://127.0.0.1:5000'])

COOKIE_NAME = 'token'

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # 1. Check cookies first
        if COOKIE_NAME in request.cookies:
            token = request.cookies[COOKIE_NAME]
            
        # 2. Fallback to Authorization header
        if not token and 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                
        if not token:
            return jsonify({'error': 'Authentication required. No token provided.'}), 401
            
        decoded = models.decode_token(token)
        if not decoded:
            return jsonify({'error': 'Invalid or expired token.'}), 401
            
        user = models.get_user_by_id(decoded['userId'])
        if not user:
            return jsonify({'error': 'User no longer exists.'}), 401
            
        # Remove password hash for safety
        user.pop('password_hash', None)
        request.user = user
        return f(*args, **kwargs)
    return decorated

def roles_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not getattr(request, 'user', None):
                return jsonify({'error': 'Authentication required.'}), 401
            if request.user['role'] not in roles:
                return jsonify({'error': 'Access denied. Insufficient permissions.'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# Serve Frontend static entry points
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

# Health Check
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'VeriList Python backend is running!'})

# Google OAuth Config (public — Client ID is not a secret)
@app.route('/api/config/google', methods=['GET'])
def google_config():
    client_id = os.getenv('GOOGLE_CLIENT_ID', '')
    configured = bool(client_id) and 'YOUR_GOOGLE_CLIENT_ID' not in client_id
    return jsonify({
        'configured': configured,
        'client_id': client_id if configured else None
    })


# Authentication API
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    role = data.get('role', 'BUYER')
    
    if not email or not password or not name:
        return jsonify({'error': 'Name, email, and password are required.'}), 400
        
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long.'}), 400
        
    if '@' not in email or '.' not in email:
        return jsonify({'error': 'Invalid email address format.'}), 400
        
    if role not in ['BUYER', 'SELLER', 'ADMIN']:
        role = 'BUYER'
        
    # Check if email exists
    if models.get_user_by_email(email):
        return jsonify({'error': 'A user with this email already exists.'}), 400
        
    pwd_hash = models.hash_password(password)
    user = models.create_user(email, pwd_hash, name, role)
    
    # Generate token
    token = models.generate_token(user['id'], user['email'], user['role'])
    
    response = make_response(jsonify({
        'message': 'User registered successfully',
        'user': user,
        'token': token
    }), 201)
    
    # Set HTTPOnly Cookie
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite='Lax',
        max_age=7 * 24 * 60 * 60, # 7 days
        path='/'
    )
    return response

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400
        
    user = models.get_user_by_email(email)
    if not user:
        return jsonify({'error': 'Invalid email or password.'}), 401
        
    if not models.check_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid email or password.'}), 401
        
    # Clean up password hash before sending
    user.pop('password_hash', None)
    
    # Generate token
    token = models.generate_token(user['id'], user['email'], user['role'])
    
    response = make_response(jsonify({
        'message': 'Login successful',
        'user': user,
        'token': token
    }))
    
    # Set HTTPOnly Cookie
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite='Lax',
        max_age=7 * 24 * 60 * 60, # 7 days
        path='/'
    )
    return response

@app.route('/api/auth/google', methods=['POST'])
def google_login():
    """Verify a real Google Access Token.
    The frontend sends: { email: "...", name: "...", access_token: "..." }
    We verify it server-side using Google's tokeninfo API to ensure authenticity.
    """
    import urllib.request
    import json

    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')

    data = request.get_json() or {}
    email = data.get('email')
    name = data.get('name')
    access_token = data.get('access_token')

    if not email or not access_token:
        return jsonify({'error': 'Email and access token are required.'}), 400

    if not GOOGLE_CLIENT_ID or 'YOUR_GOOGLE_CLIENT_ID' in GOOGLE_CLIENT_ID:
        return jsonify({
            'error': 'Google Sign-In is not configured. Please add GOOGLE_CLIENT_ID to backend/.env',
            'setup_required': True
        }), 503

    # Verify the access token server-side with Google to prevent spoofing
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                token_info = json.loads(response.read().decode('utf-8'))
                # Validate that the token was generated for our client ID
                token_client_id = token_info.get('aud') or token_info.get('client_id')
                if token_client_id != GOOGLE_CLIENT_ID:
                    return jsonify({'error': 'Google token client ID mismatch.'}), 401
                
                # Check email matches the one in token_info
                token_email = token_info.get('email')
                if not token_email or token_email.lower() != email.lower():
                    return jsonify({'error': 'Google token email mismatch.'}), 401
            else:
                return jsonify({'error': 'Failed to verify Google access token.'}), 401
    except Exception as e:
        return jsonify({'error': f'Failed to verify Google token: {str(e)}'}), 401

    email_lower = email.lower()
    user = models.get_user_by_email(email_lower)
    if not user:
        # New user — register them with selected role
        role = data.get('role', 'BUYER')
        if role not in ['BUYER', 'SELLER', 'ADMIN']:
            role = 'BUYER'
        dummy_password = str(uuid.uuid4())
        pwd_hash = models.hash_password(dummy_password)
        try:
            user = models.create_user(email_lower, pwd_hash, name or 'Google User', role)
        except Exception as e:
            return jsonify({'error': f'Failed to create user: {str(e)}'}), 500

    user.pop('password_hash', None)
    token = models.generate_token(user['id'], user['email'], user['role'])

    response = make_response(jsonify({
        'message': 'Google Login successful',
        'user': user,
        'token': token
    }))
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, samesite='Lax',
        max_age=7 * 24 * 60 * 60, path='/'
    )
    return response


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    response = make_response(jsonify({'message': 'Logged out successfully.'}))
    response.set_cookie(
        COOKIE_NAME,
        '',
        httponly=True,
        samesite='Lax',
        expires=0,
        path='/'
    )
    return response

@app.route('/api/auth/me', methods=['GET'])
@token_required
def me():
    return jsonify({'user': request.user})

@app.route('/api/auth/role', methods=['POST'])
@token_required
def switch_role():
    data = request.get_json() or {}
    role = data.get('role')
    
    if not role or role not in ['BUYER', 'SELLER']:
        return jsonify({'error': 'Invalid role. Must be BUYER or SELLER.'}), 400
        
    user_id = request.user['id']
    success = models.update_user_role(user_id, role)
    if not success:
        return jsonify({'error': 'Failed to update role.'}), 500
        
    # Re-issue JWT token with the new role
    token = models.generate_token(user_id, request.user['email'], role)
    
    # Update local request user object
    request.user['role'] = role
    
    response = make_response(jsonify({
        'message': f'Successfully switched role to {role}',
        'user': request.user,
        'token': token
    }))
    
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite='Lax',
        max_age=7 * 24 * 60 * 60, # 7 days
        path='/'
    )
    return response

# Dynamic Pricing Estimator API (for Live previews before creating listing)
@app.route('/api/ai/estimate', methods=['POST'])
@token_required
def estimate_preview():
    data = request.get_json() or {}
    year = data.get('year')
    make = data.get('make')
    model = data.get('model')
    mileage = data.get('mileage')
    condition = data.get('condition')
    
    if not year or not make or not model or not mileage or not condition:
        return jsonify({'error': 'Missing required fields for pricing estimation.'}), 400
        
    try:
        pred_price, pred_min, pred_max = PriceEstimator.estimate_price(
            int(year), str(make), str(model), int(mileage), str(condition)
        )
        return jsonify({
            'predicted_price': pred_price,
            'predicted_price_min': pred_min,
            'predicted_price_max': pred_max
        })
    except Exception as e:
        return jsonify({'error': f'Failed to calculate pricing estimate: {str(e)}'}), 500

# Listings API
@app.route('/api/listings', methods=['GET'])
def list_all():
    category = request.args.get('category')
    make = request.args.get('make')
    model = request.args.get('model')
    year_min = request.args.get('year_min')
    year_max = request.args.get('year_max')
    price_min = request.args.get('price_min')
    price_max = request.args.get('price_max')
    search = request.args.get('search')
    seller_id = request.args.get('seller_id')
    status = request.args.get('status') # Admins can specify status, buyers default to ACTIVE
    
    # Check if request has token to see if user is ADMIN for viewing PENDING_REVIEW
    req_status = 'ACTIVE'
    token = request.cookies.get(COOKIE_NAME)
    if token:
        decoded = models.decode_token(token)
        if decoded and decoded.get('role') == 'ADMIN' and status:
            req_status = status
            
    # If a seller is requesting their own listings
    if seller_id:
        req_status = status or None # Return all statuses for seller query unless specified
        
    filters = {}
    if req_status: filters['status'] = req_status
    if category: filters['category'] = category
    if make: filters['make'] = make
    if model: filters['model'] = model
    if year_min: filters['year_min'] = year_min
    if year_max: filters['year_max'] = year_max
    if price_min: filters['price_min'] = price_min
    if price_max: filters['price_max'] = price_max
    if search: filters['search'] = search
    if seller_id: filters['seller_id'] = seller_id
    
    listings = models.get_listings(filters)
    return jsonify({'listings': listings})

@app.route('/api/listings/<id>', methods=['GET'])
def get_one(id):
    listing = models.get_listing_by_id(id)
    if not listing:
        return jsonify({'error': 'Listing not found.'}), 404
        
    # Recommendation engine logic: find 3 similar listings
    # Same category, excluding current listing, sorted by price closeness
    all_active = models.get_listings({'category': listing['category'], 'status': 'ACTIVE'})
    similar = []
    for l in all_active:
        if l['id'] != listing['id']:
            # Calculate similarity score: close in price + same make gets high priority
            price_diff = abs(l['price'] - listing['price'])
            make_match = 0 if l['make'].lower() == listing['make'].lower() else 10000
            score = price_diff + make_match
            similar.append((l, score))
            
    # Sort by score ascending and take top 3
    similar.sort(key=lambda x: x[1])
    similar_listings = [item[0] for item in similar[:3]]
    
    return jsonify({
        'listing': listing,
        'similar_listings': similar_listings
    })

@app.route('/api/listings', methods=['POST'])
@token_required
@roles_required(['SELLER', 'ADMIN'])
def create():
    data = request.get_json() or {}
    title = data.get('title')
    description = data.get('description')
    price = data.get('price')
    make = data.get('make')
    model = data.get('model')
    year = data.get('year')
    mileage = data.get('mileage')
    condition = data.get('condition')
    category = data.get('category', 'VEHICLES')
    
    if not title or not description or price is None or not make or not model or not year or mileage is None or not condition:
        return jsonify({'error': 'Missing required fields for listing.'}), 400
        
    try:
        price = float(price)
        year = int(year)
        mileage = int(mileage)
    except ValueError:
        return jsonify({'error': 'Price, year, and mileage must be numbers.'}), 400
        
    # Run the AI Anomaly & Fraud detector on creation
    analysis = analyze_listing(price, year, make, model, mileage, condition, description)
    
    listing_data = {
        'title': title,
        'description': description,
        'price': price,
        'make': make,
        'model': model,
        'year': year,
        'mileage': mileage,
        'condition': condition,
        'category': category,
        'status': analysis['status'], # Will be 'PENDING_REVIEW' if trust score < 70
        'seller_id': request.user['id'],
        'trust_score': analysis['trust_score'],
        'predicted_price_min': analysis['predicted_price_min'],
        'predicted_price_max': analysis['predicted_price_max'],
        'risk_flags': analysis['risk_flags']
    }
    
    listing = models.create_listing(listing_data)
    
    status_msg = "Listing created and is live!"
    if listing['status'] == 'PENDING_REVIEW':
        status_msg = "Listing created but flagged by AI for Admin Review due to suspicious pricing/details."
        
    return jsonify({
        'message': status_msg,
        'listing': listing
    }), 201

@app.route('/api/listings/<id>', methods=['DELETE'])
@token_required
def delete(id):
    listing = models.get_listing_by_id(id)
    if not listing:
        return jsonify({'error': 'Listing not found.'}), 404
        
    # Check permissions: user must be seller or admin
    if request.user['role'] != 'ADMIN' and listing['seller_id'] != request.user['id']:
        return jsonify({'error': 'Access denied. You do not own this listing.'}), 403
        
    models.delete_listing(id)
    return jsonify({'message': 'Listing deleted successfully.'})

@app.route('/api/listings/<id>/approve', methods=['POST'])
@token_required
@roles_required(['ADMIN'])
def approve_listing(id):
    listing = models.get_listing_by_id(id)
    if not listing:
        return jsonify({'error': 'Listing not found.'}), 404
        
    models.update_listing(id, {'status': 'ACTIVE', 'trust_score': 100, 'risk_flags': []})
    return jsonify({'message': 'Listing approved by administrator and is now live!'})

# Saved Listings Toggle
@app.route('/api/listings/<id>/save', methods=['POST'])
@token_required
def toggle_save(id):
    status = models.toggle_saved_listing(request.user['id'], id)
    return jsonify({'status': status})

@app.route('/api/listings/saved', methods=['GET'])
@token_required
def get_saved():
    saved = models.get_saved_listings_for_user(request.user['id'])
    return jsonify({'listings': saved})

# Dashboard Stats API
@app.route('/api/dashboard/stats', methods=['GET'])
@token_required
def dashboard_stats():
    role = request.user['role']
    conn = models.get_db_connection()
    cursor = models.get_db_cursor(conn)
    
    stats = {}
    if role == 'ADMIN':
        # 1. Count listings pending review
        cursor.execute(models.qp('SELECT COUNT(*) FROM listings WHERE status = %s'), ('PENDING_REVIEW',))
        pending = cursor.fetchone()[0]
        # 2. Count active users
        cursor.execute(models.qp('SELECT COUNT(*) FROM users'))
        active_users = cursor.fetchone()[0]
        # 3. Sum price of all listings (volume)
        cursor.execute(models.qp('SELECT SUM(price) FROM listings WHERE status = %s'), ('ACTIVE',))
        volume = cursor.fetchone()[0] or 0.0
        
        stats = {
            'pendingReviews': pending,
            'activeUsers': active_users,
            'totalVolume': f"${volume/1000:.1f}k" if volume >= 1000 else f"${volume:.2f}"
        }
    elif role == 'SELLER':
        # 1. Count seller's active listings
        cursor.execute(models.qp('SELECT COUNT(*) FROM listings WHERE seller_id = %s AND status = %s'), (request.user['id'], 'ACTIVE'))
        active = cursor.fetchone()[0]
        # 2. Total listing views (mocked logically based on active listings)
        views = active * random.randint(35, 75) + random.randint(10, 40) if active > 0 else 0
        # 3. Seller trust rating (average trust score of active/pending listings)
        cursor.execute(models.qp('SELECT AVG(trust_score) FROM listings WHERE seller_id = %s'), (request.user['id'],))
        avg_trust = cursor.fetchone()[0]
        avg_trust = round(avg_trust, 1) if avg_trust is not None else 100.0
        
        stats = {
            'activeListings': active,
            'listingViews': views,
            'trustRating': f"{avg_trust}%"
        }
    else: # BUYER
        # 1. Count buyer's saved listings
        cursor.execute(models.qp('SELECT COUNT(*) FROM saved_listings WHERE user_id = %s'), (request.user['id'],))
        saved = cursor.fetchone()[0]
        # 2. AI Verified checks (mock count of active checked cars)
        cursor.execute(models.qp('SELECT COUNT(*) FROM listings sl JOIN saved_listings s ON s.listing_id = sl.id WHERE s.user_id = %s AND sl.trust_score >= 80'), (request.user['id'],))
        checks = cursor.fetchone()[0]
        # 3. Active offers made by buyer
        cursor.execute(models.qp('SELECT COUNT(*) FROM offers WHERE buyer_id = %s AND status = %s'), (request.user['id'], 'PENDING'))
        offers = cursor.fetchone()[0]
        
        stats = {
            'savedListings': saved,
            'aiVerifiedChecks': checks,
            'activeOffers': offers
        }
        
    conn.close()
    return jsonify({'stats': stats})

# Offers APIs
@app.route('/api/listings/<id>/offer', methods=['POST'])
@token_required
@roles_required(['BUYER'])
def make_offer(id):
    data = request.get_json() or {}
    amount = data.get('amount')
    
    if not amount:
        return jsonify({'error': 'Offer amount is required.'}), 400
        
    try:
        amount = float(amount)
    except ValueError:
        return jsonify({'error': 'Amount must be a number.'}), 400
        
    listing = models.get_listing_by_id(id)
    if not listing:
        return jsonify({'error': 'Listing not found.'}), 404
        
    offer = models.create_offer(id, request.user['id'], amount)
    return jsonify({'message': 'Offer placed successfully!', 'offer': offer}), 201

@app.route('/api/offers', methods=['GET'])
@token_required
def get_user_offers():
    offers = models.get_offers_for_user(request.user['id'], request.user['role'])
    return jsonify({'offers': offers})

@app.route('/api/offers/<id>/status', methods=['POST'])
@token_required
@roles_required(['SELLER'])
def handle_offer_status(id):
    data = request.get_json() or {}
    status = data.get('status') # 'ACCEPTED' or 'REJECTED'
    
    if status not in ['ACCEPTED', 'REJECTED']:
        return jsonify({'error': 'Invalid status. Must be ACCEPTED or REJECTED.'}), 400
        
    # Update status
    success = models.update_offer_status(id, status)
    if not success:
        return jsonify({'error': 'Offer not found.'}), 404
        
    return jsonify({'message': f'Offer {status.lower()} successfully.'})

# Mock Stripe checkout session
@app.route('/api/checkout/session', methods=['POST'])
@token_required
@roles_required(['BUYER'])
def create_checkout_session():
    data = request.get_json() or {}
    listing_id = data.get('listing_id')
    
    if not listing_id:
        return jsonify({'error': 'Listing ID is required.'}), 400
        
    listing = models.get_listing_by_id(listing_id)
    if not listing:
        return jsonify({'error': 'Listing not found.'}), 404
        
    # Simulate payment processing - update listing status to SOLD
    models.update_listing_status(listing_id, 'SOLD')
    
    # Return mock Stripe checkout redirect info
    return jsonify({
        'session_id': f"cs_test_{str(uuid.uuid4())}",
        'success_url': '/#dashboard?payment=success',
        'cancel_url': '/#listings'
    })

# Serve static assets from frontend
@app.route('/<path:path>')
def serve_static(path):
    # If the file exists in the frontend folder, serve it
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    # Otherwise, fallback to serving index.html for SPA routing support
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    print("Starting VeriList Python Server on http://localhost:5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)
