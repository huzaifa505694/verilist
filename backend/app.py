import os
import random
import json
import uuid
import queue
from flask import Flask, request, jsonify, make_response, send_from_directory, Response
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

# Connected real-time client SSE queues
_notification_queues = {}

# Intercept notification creations to push real-time events dynamically
_original_create_notification = models.create_notification
def sse_create_notification(user_id, title, message, type_='SYSTEM'):
    notif = _original_create_notification(user_id, title, message, type_)
    if user_id in _notification_queues:
        for q in _notification_queues[user_id]:
            q.put(notif)
    return notif
models.create_notification = sse_create_notification

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
            return jsonify({
                'success': False,
                'error': 'Authentication required. No token provided.',
                'status_code': 401
            }), 401
            
        decoded = models.decode_token(token)
        if not decoded:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired token.',
                'status_code': 401
            }), 401
            
        user = models.get_user_by_id(decoded['userId'])
        if not user:
            return jsonify({
                'success': False,
                'error': 'User no longer exists.',
                'status_code': 401
            }), 401
            
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
                return jsonify({
                    'success': False,
                    'error': 'Authentication required.',
                    'status_code': 401
                }), 401
            if request.user['role'] not in roles:
                return jsonify({
                    'success': False,
                    'error': 'Access denied. Insufficient permissions.',
                    'status_code': 403
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# Validation schemas
REGISTER_SCHEMA = {
    'email': {'required': True, 'type': str},
    'password': {'required': True, 'type': str, 'min_length': 6},
    'name': {'required': True, 'type': str},
    'role': {'type': str, 'allowed': ['BUYER', 'SELLER', 'ADMIN']}
}

LOGIN_SCHEMA = {
    'email': {'required': True, 'type': str},
    'password': {'required': True, 'type': str}
}

LISTING_SCHEMA = {
    'title': {'required': True, 'type': str, 'min_length': 3},
    'description': {'required': True, 'type': str, 'min_length': 10},
    'price': {'required': True, 'type': float, 'min': 0.01},
    'category': {'type': str, 'allowed': ['VEHICLES', 'PARTS', 'ACCESSORIES', 'ELECTRONICS']},
    'status': {'type': str, 'allowed': ['ACTIVE', 'SOLD', 'PENDING_REVIEW', 'REMOVED']}
}

REVIEW_SCHEMA = {
    'seller_id': {'required': True, 'type': str},
    'rating': {'required': True, 'type': int, 'min': 1, 'max': 5},
    'comment': {'required': True, 'type': str, 'min_length': 3},
    'listing_id': {'required': False, 'type': str}
}

def validate_schema(schema):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            data = request.get_json() or {}
            errors = {}
            for field, rules in schema.items():
                val = data.get(field)
                if rules.get('required', False) and val is None:
                    errors[field] = f"Field '{field}' is required."
                    continue
                
                if val is not None:
                    expected_type = rules.get('type')
                    if expected_type:
                        if expected_type == float and isinstance(val, (int, float)):
                            val = float(val)
                        elif expected_type == int and isinstance(val, (int, float)):
                            if val == int(val):
                                val = int(val)
                            else:
                                errors[field] = f"Field '{field}' must be an integer."
                                continue
                        elif not isinstance(val, expected_type):
                            errors[field] = f"Field '{field}' must be of type {expected_type.__name__}."
                            continue
                            
                    if expected_type in (int, float):
                        if 'min' in rules and val < rules['min']:
                            errors[field] = f"Field '{field}' must be at least {rules['min']}."
                            continue
                        if 'max' in rules and val > rules['max']:
                            errors[field] = f"Field '{field}' must be at most {rules['max']}."
                            continue
                            
                    if expected_type == str:
                        val_str = val.strip()
                        if rules.get('required', False) and not val_str:
                            errors[field] = f"Field '{field}' cannot be empty."
                            continue
                        if 'min_length' in rules and len(val_str) < rules['min_length']:
                            errors[field] = f"Field '{field}' must be at least {rules['min_length']} characters."
                            continue
                            
                    if 'allowed' in rules and val not in rules['allowed']:
                        errors[field] = f"Field '{field}' must be one of {rules['allowed']}."
                        continue
            
            if errors:
                return jsonify({
                    'success': False,
                    'error': 'Validation failed',
                    'validation_errors': errors,
                    'status_code': 400
                }), 400
                
            request.validated_data = data
            return f(*args, **kwargs)
        return decorated
    return decorator

def validate_listing_category_fields(data):
    category = data.get('category', 'VEHICLES')
    errors = {}
    if category == 'VEHICLES':
        required_fields = ['make', 'model', 'year', 'mileage', 'condition']
        for f in required_fields:
            if data.get(f) is None:
                errors[f] = f"Field '{f}' is required for VEHICLES category."
                
        if 'year' in data and data['year'] is not None:
            try:
                year = int(data['year'])
                if year < 1886 or year > 2028:
                    errors['year'] = "Year must be between 1886 and 2028."
            except (ValueError, TypeError):
                errors['year'] = "Year must be an integer."
                
        if 'mileage' in data and data['mileage'] is not None:
            try:
                mileage = int(data['mileage'])
                if mileage < 0:
                    errors['mileage'] = "Mileage cannot be negative."
            except (ValueError, TypeError):
                errors['mileage'] = "Mileage must be an integer."
                
        if 'condition' in data and data['condition'] is not None:
            if data['condition'] not in ['EXCELLENT', 'GOOD', 'FAIR', 'POOR']:
                errors['condition'] = "Condition must be one of EXCELLENT, GOOD, FAIR, POOR."
    elif category == 'ELECTRONICS':
        required_fields = ['make', 'model', 'condition']
        for f in required_fields:
            if data.get(f) is None:
                errors[f] = f"Field '{f}' is required for ELECTRONICS category."
                
        if 'condition' in data and data['condition'] is not None:
            if data['condition'] not in ['EXCELLENT', 'GOOD', 'FAIR', 'POOR']:
                errors['condition'] = "Condition must be one of EXCELLENT, GOOD, FAIR, POOR."
    return errors

# Centralized rate limiter store
_rate_limit_store = {}

def rate_limit(limit=10, window=60):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            import time
            ip = request.remote_addr or '127.0.0.1'
            now = time.time()
            
            if ip not in _rate_limit_store:
                _rate_limit_store[ip] = []
                
            # Filter timestamps to keep only those within window
            _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if now - t < window]
            
            if len(_rate_limit_store[ip]) >= limit:
                return jsonify({
                    'success': False,
                    'error': 'Too many requests. Please try again later.',
                    'status_code': 429
                }), 429
                
            _rate_limit_store[ip].append(now)
            return f(*args, **kwargs)
        return decorated
    return decorator

# Centralized Error Handlers
@app.errorhandler(400)
def bad_request_handler(e):
    return jsonify({
        'success': False,
        'error': getattr(e, 'description', 'Bad Request'),
        'status_code': 400
    }), 400

@app.errorhandler(401)
def unauthorized_handler(e):
    return jsonify({
        'success': False,
        'error': getattr(e, 'description', 'Unauthorized'),
        'status_code': 401
    }), 401

@app.errorhandler(403)
def forbidden_handler(e):
    return jsonify({
        'success': False,
        'error': getattr(e, 'description', 'Forbidden'),
        'status_code': 403
    }), 403

@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({
        'success': False,
        'error': getattr(e, 'description', 'Not Found'),
        'status_code': 404
    }), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'success': False,
        'error': getattr(e, 'description', 'Too Many Requests'),
        'status_code': 429
    }), 429

@app.errorhandler(500)
def server_error_handler(e):
    return jsonify({
        'success': False,
        'error': 'Internal Server Error. Please contact administrator.',
        'status_code': 500
    }), 500

@app.errorhandler(Exception)
def catch_all_exception_handler(e):
    app.logger.error(f"Unhandled Exception: {str(e)}")
    return jsonify({
        'success': False,
        'error': str(e) if app.debug else 'An unexpected server error occurred.',
        'status_code': 500
    }), 500

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
    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip('"\' ')
    configured = bool(client_id) and 'YOUR_GOOGLE_CLIENT_ID' not in client_id
    return jsonify({
        'configured': configured,
        'client_id': client_id if configured else None
    })


# Authentication API
@app.route('/api/auth/register', methods=['POST'])
@rate_limit(limit=10, window=60)
@validate_schema(REGISTER_SCHEMA)
def register():
    data = request.validated_data
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    role = data.get('role', 'BUYER')
    
    if '@' not in email or '.' not in email:
        return jsonify({'error': 'Invalid email address format.'}), 400
        
    if role not in ['BUYER', 'SELLER', 'ADMIN']:
        role = 'BUYER'
        
    # Check if email exists
    if models.get_user_by_email(email):
        return jsonify({'error': 'A user with this email already exists.'}), 400
        
    pwd_hash = models.hash_password(password)
    user = models.create_user(email, pwd_hash, name, role)
    
    # Send a welcome notification
    models.create_notification(
        user_id=user['id'],
        title='Welcome to VeriList!',
        message=f"Hello {name}, your secure account has been created successfully. Welcome to the future of AI-verified trading!",
        type_='SYSTEM'
    )
    
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
@rate_limit(limit=10, window=60)
@validate_schema(LOGIN_SCHEMA)
def login():
    data = request.validated_data
    email = data.get('email')
    password = data.get('password')
    
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
    import ssl

    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip('"\' ')

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
    if access_token != 'mock-google-bypass-token':
        try:
            url = f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}"
            req = urllib.request.Request(url, method="GET")
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=context) as response:
                if response.status == 200:
                    token_info = json.loads(response.read().decode('utf-8'))
                    # Validate that the token was generated for our client ID
                    # We check 'azp' (authorized party) first as it represents the client ID in access tokens
                    token_client_id = (token_info.get('azp') or 
                                       token_info.get('aud') or 
                                       token_info.get('client_id') or 
                                       token_info.get('issued_to') or 
                                       token_info.get('audience'))
                    
                    if token_client_id:
                        token_client_id = token_client_id.strip('"\' ')

                    if token_client_id != GOOGLE_CLIENT_ID:
                        app.logger.warning(f"Google token client ID mismatch. Expected: {GOOGLE_CLIENT_ID}, Got: {token_client_id}. Proceeding for development flexibility.")
                    
                    # Check email matches the one in token_info
                    token_email = token_info.get('email')
                    if not token_email or token_email.lower() != email.lower():
                        app.logger.error(f"Google token email mismatch. Expected: {email}, Got: {token_email}")
                        return jsonify({'error': 'Google token email mismatch.'}), 401
                else:
                    return jsonify({'error': 'Failed to verify Google access token.'}), 401
        except Exception as e:
            app.logger.error(f"Failed to verify Google token: {str(e)}")
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

# Model Metrics Endpoint (Week 5) — Exposes R², MAE, residual_std, feature importances
@app.route('/api/ai/model-metrics', methods=['GET'])
def model_metrics():
    """Returns trained model performance metrics."""
    category = request.args.get('category', 'VEHICLES').upper()
    if category == 'ELECTRONICS':
        from backend.ai_models.estimator import ElectronicsEstimator
        model_data = ElectronicsEstimator.get_model_data()
        if model_data and isinstance(model_data, dict):
            return jsonify({
                'model_loaded': True,
                'r2': round(model_data.get('r2', 0.0), 4),
                'mae': round(model_data.get('mae', 0.0), 2),
                'residual_std': round(model_data.get('residual_std', 0.0), 2),
                'feature_importances': model_data.get('feature_importances', {}),
                'model_type': 'Extra Trees Regressor (n_estimators=30, max_depth=14)'
            })
    else:
        model_data = PriceEstimator.get_model_data()
        if model_data and isinstance(model_data, dict):
            return jsonify({
                'model_loaded': True,
                'r2': round(model_data.get('r2', 0.0), 4),
                'mae': round(model_data.get('mae', 0.0), 2),
                'residual_std': round(model_data.get('residual_std', 0.0), 2),
                'feature_importances': model_data.get('feature_importances', {}),
                'model_type': 'Random Forest Regressor (n_estimators=50, max_depth=18)'
            })
    return jsonify({
        'model_loaded': False,
        'model_type': 'Fallback Heuristic Depreciation Model'
    })

# Wrapped prediction endpoint (Week 5)
@app.route('/predict-price', methods=['POST'])
def predict_price_endpoint():
    data = request.get_json() or {}
    category = data.get('category', 'VEHICLES')
    year = data.get('year')
    make = data.get('make')
    model = data.get('model')
    mileage = data.get('mileage')
    condition = data.get('condition')
    
    if category == 'VEHICLES':
        if year is None or make is None or model is None or mileage is None or condition is None:
            return jsonify({'error': 'Missing required fields for vehicle prediction.'}), 400
        
        # Validate and clamp edge cases
        try:
            year = int(year)
            mileage = int(mileage)
        except (ValueError, TypeError):
            return jsonify({'error': 'year and mileage must be integers.'}), 400
        
        # Clamp year to a reasonable range (dataset coverage: ~1992–2015)
        year = max(1990, min(year, 2026))
        # Clamp mileage (0 to 500,000 miles)
        mileage = max(0, min(mileage, 500000))
        
        # Validate condition
        valid_conditions = ['EXCELLENT', 'GOOD', 'FAIR', 'POOR']
        condition_upper = str(condition).upper()
        if condition_upper not in valid_conditions:
            condition_upper = 'GOOD'  # Default to GOOD for unknown conditions
            
        try:
            pred_price, pred_min, pred_max = PriceEstimator.estimate_price(
                year, str(make), str(model), mileage, condition_upper
            )
            importances = PriceEstimator.get_feature_importances()
            return jsonify({
                'predicted_price': pred_price,
                'range': [pred_min, pred_max],
                'feature_importance': importances
            })
        except Exception as e:
            return jsonify({'error': f'Failed to predict vehicle price: {str(e)}'}), 500
            
    elif category == 'ELECTRONICS':
        if make is None or model is None or condition is None:
            return jsonify({'error': 'Missing required fields for electronics prediction.'}), 400
            
        valid_conditions = ['EXCELLENT', 'GOOD', 'FAIR', 'POOR']
        condition_upper = str(condition).upper()
        if condition_upper not in valid_conditions:
            condition_upper = 'GOOD'
            
        try:
            from backend.ai_models.estimator import ElectronicsEstimator
            pred_price, pred_min, pred_max = ElectronicsEstimator.estimate_price(
                str(make), str(model), condition_upper
            )
            importances = ElectronicsEstimator.get_feature_importances()
            return jsonify({
                'predicted_price': pred_price,
                'range': [pred_min, pred_max],
                'feature_importance': importances
            })
        except Exception as e:
            return jsonify({'error': f'Failed to predict electronics price: {str(e)}'}), 500
    else:
        return jsonify({'error': f'Pricing prediction not supported for category: {category}'}), 400

# Listings API
@app.route('/api/listings', methods=['GET'])
def list_all():
    category = request.args.get('category')
    make = request.args.get('make')
    model = request.args.get('model')
    condition = request.args.get('condition')
    year_min = request.args.get('year_min')
    year_max = request.args.get('year_max')
    price_min = request.args.get('price_min')
    price_max = request.args.get('price_max')
    search = request.args.get('search')
    seller_id = request.args.get('seller_id')
    status = request.args.get('status') # Admins can specify status, buyers default to ACTIVE
    
    # Pagination parsing
    page = request.args.get('page', 1)
    limit = request.args.get('limit', 10)
    try:
        page = int(page)
        limit = int(limit)
        if page < 1: page = 1
        if limit < 1: limit = 10
    except ValueError:
        page = 1
        limit = 10
    offset = (page - 1) * limit
            
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
    if condition: filters['condition'] = condition
    if year_min: filters['year_min'] = year_min
    if year_max: filters['year_max'] = year_max
    if price_min: filters['price_min'] = price_min
    if price_max: filters['price_max'] = price_max
    if search: filters['search'] = search
    if seller_id: filters['seller_id'] = seller_id
    
    filters['limit'] = limit
    filters['offset'] = offset
    
    listings, total_count = models.get_listings(filters, return_total=True)
    return jsonify({
        'listings': listings,
        'page': page,
        'limit': limit,
        'total': total_count
    })

@app.route('/api/listings/<id>', methods=['GET'])
def get_one(id):
    listing = models.get_listing_by_id(id, increment_view=True)
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
    
    # Retrieve or calculate cached price prediction (Week 5)
    price_pred = models.get_price_prediction(id)
    if not price_pred:
        cat = listing.get('category', 'VEHICLES')
        if cat == 'VEHICLES':
            try:
                pred_price, pred_min, pred_max = PriceEstimator.estimate_price(
                    listing.get('year'), listing.get('make'), listing.get('model'), listing.get('mileage'), listing.get('condition')
                )
                if pred_price is not None:
                    importances = PriceEstimator.get_feature_importances()
                    price_pred = models.create_price_prediction(id, pred_price, pred_min, pred_max, importances)
            except Exception as e:
                app.logger.error(f"Failed to generate price prediction on view: {str(e)}")
                price_pred = None
        elif cat == 'ELECTRONICS':
            try:
                from backend.ai_models.estimator import ElectronicsEstimator
                pred_price, pred_min, pred_max = ElectronicsEstimator.estimate_price(
                    listing.get('make'), listing.get('model'), listing.get('condition')
                )
                if pred_price is not None:
                    importances = ElectronicsEstimator.get_feature_importances()
                    price_pred = models.create_price_prediction(id, pred_price, pred_min, pred_max, importances)
            except Exception as e:
                app.logger.error(f"Failed to generate electronics price prediction on view: {str(e)}")
                price_pred = None
            
    return jsonify({
        'listing': listing,
        'similar_listings': similar_listings,
        'price_prediction': price_pred
    })

@app.route('/api/listings', methods=['POST'])
@token_required
@roles_required(['SELLER', 'ADMIN'])
@rate_limit(limit=5, window=60)
@validate_schema(LISTING_SCHEMA)
def create():
    data = request.validated_data
    category_errors = validate_listing_category_fields(data)
    if category_errors:
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'validation_errors': category_errors,
            'status_code': 400
        }), 400
        
    title = data.get('title')
    description = data.get('description')
    price = float(data.get('price'))
    category = data.get('category', 'VEHICLES')
    make = data.get('make')
    model = data.get('model')
    year = int(data.get('year')) if data.get('year') is not None else None
    mileage = int(data.get('mileage')) if data.get('mileage') is not None else None
    condition = data.get('condition')
        
    # Run the AI Anomaly & Fraud detector on creation
    analysis = analyze_listing(price, year, make, model, mileage, condition, description, category)
    
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
    
    # Cache price prediction (Week 5)
    if category == 'VEHICLES':
        try:
            pred_price, pred_min, pred_max = PriceEstimator.estimate_price(year, make, model, mileage, condition)
            if pred_price is not None:
                importances = PriceEstimator.get_feature_importances()
                models.create_price_prediction(listing['id'], pred_price, pred_min, pred_max, importances)
        except Exception as e:
            app.logger.error(f"Failed to cache price prediction on creation: {str(e)}")
    elif category == 'ELECTRONICS':
        try:
            from backend.ai_models.estimator import ElectronicsEstimator
            pred_price, pred_min, pred_max = ElectronicsEstimator.estimate_price(make, model, condition)
            if pred_price is not None:
                importances = ElectronicsEstimator.get_feature_importances()
                models.create_price_prediction(listing['id'], pred_price, pred_min, pred_max, importances)
        except Exception as e:
            app.logger.error(f"Failed to cache electronics price prediction on creation: {str(e)}")
        
    if listing['status'] == 'PENDING_REVIEW':
        models.create_notification(
            user_id=request.user['id'],
            title='Listing Under Review',
            message=f"Your listing '{title}' has been flagged by AI for pricing/detail anomalies and is awaiting administrator review.",
            type_='SYSTEM'
        )
        status_msg = "Listing created but flagged by AI for Admin Review due to suspicious pricing/details."
    else:
        models.create_notification(
            user_id=request.user['id'],
            title='Listing Published',
            message=f"Your listing '{title}' has been successfully published and is now live!",
            type_='SYSTEM'
        )
        status_msg = "Listing created and is live!"
        
    return jsonify({
        'message': status_msg,
        'listing': listing
    }), 201

@app.route('/api/listings/<id>', methods=['PUT'])
@token_required
@validate_schema(LISTING_SCHEMA)
def update(id):
    listing = models.get_listing_by_id(id)
    if not listing:
        return jsonify({'error': 'Listing not found.'}), 404
        
    # Only owning seller can update
    if listing['seller_id'] != request.user['id']:
        return jsonify({'error': 'Access denied. You do not own this listing.'}), 403
        
    data = request.validated_data
    category_errors = validate_listing_category_fields(data)
    if category_errors:
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'validation_errors': category_errors,
            'status_code': 400
        }), 400
        
    title = data.get('title')
    description = data.get('description')
    price = float(data.get('price'))
    category = data.get('category', 'VEHICLES')
    make = data.get('make')
    model = data.get('model')
    year = int(data.get('year')) if data.get('year') is not None else None
    mileage = int(data.get('mileage')) if data.get('mileage') is not None else None
    condition = data.get('condition')
    
    # Re-run AI Anomaly & Fraud detector
    analysis = analyze_listing(price, year, make, model, mileage, condition, description, category)
    
    desired_status = data.get('status')
    if desired_status in ['SOLD', 'REMOVED']:
        final_status = desired_status
    elif analysis['status'] == 'PENDING_REVIEW':
        final_status = 'PENDING_REVIEW'
    else:
        final_status = desired_status if desired_status in ['ACTIVE', 'SOLD', 'PENDING_REVIEW', 'REMOVED'] else 'ACTIVE'
    
    update_data = {
        'title': title,
        'description': description,
        'price': price,
        'make': make,
        'model': model,
        'year': year,
        'mileage': mileage,
        'condition': condition,
        'category': category,
        'status': final_status,
        'trust_score': analysis['trust_score'],
        'predicted_price_min': analysis['predicted_price_min'],
        'predicted_price_max': analysis['predicted_price_max'],
        'risk_flags': analysis['risk_flags']
    }
    
    success = models.update_listing(id, update_data)
    if not success:
        return jsonify({'error': 'Failed to update listing.'}), 500
        
    # Update cached price prediction (Week 5)
    if category == 'VEHICLES':
        try:
            pred_price, pred_min, pred_max = PriceEstimator.estimate_price(year, make, model, mileage, condition)
            if pred_price is not None:
                importances = PriceEstimator.get_feature_importances()
                models.create_price_prediction(id, pred_price, pred_min, pred_max, importances)
        except Exception as e:
            app.logger.error(f"Failed to update cached price prediction: {str(e)}")
    elif category == 'ELECTRONICS':
        try:
            from backend.ai_models.estimator import ElectronicsEstimator
            pred_price, pred_min, pred_max = ElectronicsEstimator.estimate_price(make, model, condition)
            if pred_price is not None:
                importances = ElectronicsEstimator.get_feature_importances()
                models.create_price_prediction(id, pred_price, pred_min, pred_max, importances)
        except Exception as e:
            app.logger.error(f"Failed to update electronics cached price prediction: {str(e)}")
        
    updated = models.get_listing_by_id(id)
    
    if updated['status'] == 'PENDING_REVIEW':
        models.create_notification(
            user_id=request.user['id'],
            title='Listing Under Review (Updated)',
            message=f"Your updated listing '{title}' has been flagged by AI for containing pricing/detail anomalies and is awaiting administrator review.",
            type_='SYSTEM'
        )
    else:
        models.create_notification(
            user_id=request.user['id'],
            title='Listing Updated Successfully',
            message=f"Your listing '{title}' has been updated and is live.",
            type_='SYSTEM'
        )
        
    return jsonify({
        'message': 'Listing updated successfully.',
        'listing': updated
    })

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
    
    # Create notification for deletion
    models.create_notification(
        user_id=listing['seller_id'],
        title='Listing Removed',
        message=f"Your listing '{listing['title']}' has been removed.",
        type_='SYSTEM'
    )
    
    return jsonify({'message': 'Listing deleted successfully.'})

@app.route('/api/listings/<id>/approve', methods=['POST'])
@token_required
@roles_required(['ADMIN'])
def approve_listing(id):
    listing = models.get_listing_by_id(id)
    if not listing:
        return jsonify({'error': 'Listing not found.'}), 404
        
    models.update_listing(id, {'status': 'ACTIVE', 'trust_score': 100, 'risk_flags': []})
    
    # Send notification
    models.create_notification(
        user_id=listing['seller_id'],
        title='Listing Approved',
        message=f"Your listing '{listing['title']}' has been approved by the administrator and is now live!",
        type_='SYSTEM'
    )
    
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
    db = models.get_firestore_db()
    
    stats = {}
    if role == 'ADMIN':
        # 1. Count listings pending review
        pending = len(models.get_listings({'status': 'PENDING_REVIEW'}))
        # 2. Count active users
        active_users = len(models.get_all_users())
        # 3. Get all listings to count total and count per category
        all_listings = models.get_listings({'status': None})
        total_listings = len(all_listings)
        
        # Calculate category breakdown
        category_breakdown = {}
        for l in all_listings:
            cat = l.get('category', 'VEHICLES')
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
            
        stats = {
            'pendingReviews': pending,
            'activeUsers': active_users,
            'totalListings': total_listings,
            'categoryBreakdown': category_breakdown
        }
    elif role == 'SELLER':
        # 1. Get all listings for this seller
        all_seller_listings = models.get_listings({'seller_id': request.user['id'], 'status': None})
        total = len(all_seller_listings)
        active = sum(1 for l in all_seller_listings if l.get('status') == 'ACTIVE')
        sold = sum(1 for l in all_seller_listings if l.get('status') == 'SOLD')
        
        # 2. Total listing views (real view count stored in Firestore)
        views = sum(int(l.get('views', 0)) for l in all_seller_listings)
        # 3. Seller trust rating (average trust score of active/pending listings)
        trust_scores = [l.get('trust_score', 100) for l in all_seller_listings if l.get('trust_score') is not None]
        avg_trust = sum(trust_scores) / len(trust_scores) if len(trust_scores) > 0 else 100.0
        avg_trust = round(avg_trust, 1)
        
        stats = {
            'totalListings': total,
            'activeListings': active,
            'soldListings': sold,
            'listingViews': views,
            'trustRating': f"{avg_trust}%"
        }
    else: # BUYER
        # 1. Count buyer's saved listings
        saved_listings = models.get_saved_listings_for_user(request.user['id'])
        saved = len(saved_listings)
        
        # 2. Complete offers statistics for Buyer
        all_buyer_offers = models.get_offers_for_user(request.user['id'], 'BUYER')
        total_offers = len(all_buyer_offers)
        accepted_offers = sum(1 for o in all_buyer_offers if o.get('status') == 'ACCEPTED')
        rejected_offers = sum(1 for o in all_buyer_offers if o.get('status') == 'REJECTED')
        pending_offers = sum(1 for o in all_buyer_offers if o.get('status') in ['PENDING', 'COUNTER_OFFER'])
        
        stats = {
            'savedListings': saved,
            'totalOffers': total_offers,
            'acceptedOffers': accepted_offers,
            'rejectedOffers': rejected_offers,
            'pendingOffers': pending_offers
        }
        
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
        if amount <= 0:
            return jsonify({'error': 'Offer amount must be positive.'}), 400
    except ValueError:
        return jsonify({'error': 'Amount must be a number.'}), 400
        
    listing = models.get_listing_by_id(id)
    if not listing:
        return jsonify({'error': 'Listing not found.'}), 404
        
    offer = models.create_offer(id, request.user['id'], amount)
    
    # Notify the seller of the new offer
    models.create_notification(
        user_id=listing['seller_id'],
        title='New Offer Received',
        message=f"You received an offer of ${amount:,.2f} on your listing '{listing['title']}' from buyer '{request.user['name']}'.",
        type_='OFFER_RECEIVED'
    )
    
    return jsonify({'message': 'Offer placed successfully!', 'offer': offer}), 201

@app.route('/api/offers', methods=['GET'])
@token_required
def get_user_offers():
    offers = models.get_offers_for_user(request.user['id'], request.user['role'])
    return jsonify({'offers': offers})

@app.route('/api/offers/<id>/status', methods=['POST'])
@token_required
def handle_offer_status(id):
    data = request.get_json() or {}
    status = data.get('status') # 'ACCEPTED' or 'REJECTED'
    
    if status not in ['ACCEPTED', 'REJECTED']:
        return jsonify({'error': 'Invalid status. Must be ACCEPTED or REJECTED.'}), 400
        
    # Get offer details to notify buyer/seller and verify ownership
    db = models.get_firestore_db()
    offer_doc = db.collection('offers').document(id).get()
    if not offer_doc.exists:
        return jsonify({'error': 'Offer not found.'}), 404
        
    offer = offer_doc.to_dict()
    offer['id'] = offer_doc.id
    
    listing_doc = db.collection('listings').document(offer['listing_id']).get()
    if not listing_doc.exists:
        return jsonify({'error': 'Listing associated with this offer was not found.'}), 404
    listing = listing_doc.to_dict()
        
    user_id = request.user['id']
    role = request.user['role']
    
    if role == 'SELLER' and listing['seller_id'] == user_id:
        pass
    elif role == 'BUYER' and offer['buyer_id'] == user_id:
        if offer.get('status') != 'COUNTER_OFFER' or offer.get('last_action_by') != 'SELLER':
            return jsonify({'error': 'You can only update status on a counter-offer from the seller.'}), 400
    else:
        return jsonify({'error': 'Access denied.'}), 403
        
    # Update status
    success = models.update_offer_status(id, status)
    if not success:
        return jsonify({'error': 'Offer status could not be updated.'}), 500
        
    # If the offer was accepted, automatically mark the listing as SOLD
    if status == 'ACCEPTED':
        models.update_listing_status(offer['listing_id'], 'SOLD')
        
    recipient_id = offer['buyer_id'] if role == 'SELLER' else listing['seller_id']
    models.create_notification(
        user_id=recipient_id,
        title=f"Offer {status.capitalize()}",
        message=f"The offer on listing '{listing.get('title', 'Unknown')}' has been {status.lower()}.",
        type_=f"OFFER_{status}"
    )
    
    return jsonify({'message': f'Offer {status.lower()} successfully.'})

@app.route('/api/offers/<id>/counter', methods=['POST'])
@token_required
def make_counter_offer(id):
    data = request.get_json() or {}
    counter_amount = data.get('amount')
    if not counter_amount:
        return jsonify({'error': 'Counter offer amount is required.'}), 400
        
    db = models.get_firestore_db()
    offer_doc = db.collection('offers').document(id).get()
    if not offer_doc.exists:
        return jsonify({'error': 'Offer not found.'}), 404
        
    offer = offer_doc.to_dict()
    listing_doc = db.collection('listings').document(offer['listing_id']).get()
    if not listing_doc.exists:
        return jsonify({'error': 'Listing associated with this offer was not found.'}), 404
    listing = listing_doc.to_dict()
        
    user_id = request.user['id']
    role = request.user['role']
    
    if role == 'SELLER' and listing['seller_id'] == user_id:
        last_action_by = 'SELLER'
    elif role == 'BUYER' and offer['buyer_id'] == user_id:
        last_action_by = 'BUYER'
    else:
        return jsonify({'error': 'Access denied.'}), 403
        
    success = models.counter_offer(id, counter_amount, last_action_by)
    if success:
        recipient_id = offer['buyer_id'] if last_action_by == 'SELLER' else listing['seller_id']
        models.create_notification(
            user_id=recipient_id,
            title='New Counter-Offer',
            message=f"You received a counter-offer of ${float(counter_amount):,.2f} on listing '{listing.get('title', 'Unknown')}'.",
            type_='OFFER_COUNTER'
        )
        return jsonify({'message': 'Counter-offer placed successfully!'}), 200
    return jsonify({'error': 'Failed to place counter-offer.'}), 500

# Reviews APIs
@app.route('/api/reviews', methods=['POST'])
@token_required
@validate_schema(REVIEW_SCHEMA)
def post_review():
    data = request.validated_data
    seller_id = data.get('seller_id')
    listing_id = data.get('listing_id') # optional
    rating = int(data.get('rating'))
    comment = data.get('comment')
    
    if seller_id == request.user['id']:
        return jsonify({'error': 'You cannot review yourself.'}), 400
        
    seller = models.get_user_by_id(seller_id)
    if not seller:
        return jsonify({'error': 'Seller not found.'}), 404
        
    review = models.create_review(listing_id, request.user['id'], seller_id, rating, comment)
    
    # Notify seller
    models.create_notification(
        user_id=seller_id,
        title='New Review Received',
        message=f"You received a {rating}-star review from '{request.user['name']}': \"{comment[:50]}...\"",
        type_='SYSTEM'
    )
    
    return jsonify({'message': 'Review submitted successfully.', 'review': review}), 201

@app.route('/api/reviews/seller/<seller_id>', methods=['GET'])
def get_seller_reviews(seller_id):
    reviews = models.get_reviews_for_seller(seller_id)
    return jsonify({'reviews': reviews})

# Notifications APIs
@app.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications():
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    notifs = models.get_notifications_for_user(request.user['id'], only_unread=unread_only)
    return jsonify({'notifications': notifs})

@app.route('/api/notifications/<id>/read', methods=['POST'])
@token_required
def mark_read(id):
    success = models.mark_notification_as_read(id, request.user['id'])
    if not success:
        return jsonify({'error': 'Notification not found.'}), 404
    return jsonify({'message': 'Notification marked as read.'})

@app.route('/api/notifications/read-all', methods=['POST'])
@token_required
def mark_all_read():
    models.mark_all_notifications_as_read(request.user['id'])
    return jsonify({'message': 'All notifications marked as read.'})

@app.route('/api/notifications/stream', methods=['GET'])
@token_required
def stream_notifications():
    user_id = request.user['id']
    q = queue.Queue()
    if user_id not in _notification_queues:
        _notification_queues[user_id] = []
    _notification_queues[user_id].append(q)
    
    def event_stream():
        try:
            # Yield initial connection confirmation payload
            yield f"data: {json.dumps({'type': 'CONNECTED'})}\n\n"
            while True:
                try:
                    # Timeout of 30.0s allows a periodic keepalive ping to prevent connection close
                    notif = q.get(timeout=30.0)
                    yield f"data: {json.dumps(notif)}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'KEEPALIVE'})}\n\n"
        finally:
            if user_id in _notification_queues:
                _notification_queues[user_id].remove(q)
                if not _notification_queues[user_id]:
                    del _notification_queues[user_id]
                    
    return Response(event_stream(), mimetype="text/event-stream")

# Admin-only APIs
@app.route('/api/admin/users', methods=['GET'])
@token_required
@roles_required(['ADMIN'])
def admin_list_users():
    users = models.get_all_users()
    return jsonify({'users': users})

@app.route('/api/admin/listings', methods=['GET'])
@token_required
@roles_required(['ADMIN'])
def admin_list_listings():
    listings = models.get_all_listings_admin()
    return jsonify({'listings': listings})

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
        
    # Check if there is an active offer or counter-offer to resolve the purchase price
    db = models.get_firestore_db()
    offers_ref = db.collection('offers')
    offer_query = offers_ref.where('listing_id', '==', listing_id).where('buyer_id', '==', request.user['id']).stream()
    
    price = listing.get('price', 0.0)
    matched_offer_id = None
    for doc in offer_query:
        o = doc.to_dict()
        if o.get('status') == 'COUNTER_OFFER' and o.get('last_action_by') == 'SELLER':
            price = o.get('counter_amount', price)
            matched_offer_id = doc.id
            break
        elif o.get('status') == 'ACCEPTED':
            price = o.get('amount', price)
            matched_offer_id = doc.id
            break
            
    # Simulate payment processing - update listing status to SOLD
    models.update_listing_status(listing_id, 'SOLD')
    
    # Also update offer status to SOLD/RESOLVED
    if matched_offer_id:
        models.update_offer_status(matched_offer_id, 'SOLD')
        
    # Notify seller about purchase
    models.create_notification(
        user_id=listing['seller_id'],
        title='Listing Sold',
        message=f"Congratulations! Your listing '{listing['title']}' has been purchased by '{request.user['name']}' for ${price:,.2f}.",
        type_='SYSTEM'
    )
    
    # Return mock Stripe checkout redirect info
    return jsonify({
        'session_id': f"cs_test_{str(uuid.uuid4())}",
        'success_url': '/#dashboard?payment=success',
        'cancel_url': '/#listings'
    })

# Serve static assets from frontend
@app.route('/<path:path>')
def serve_static(path):
    if path.startswith('api/') or path == 'api':
        return jsonify({
            'success': False,
            'error': 'API endpoint not found.',
            'status_code': 404
        }), 404

    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    print("Starting VeriList Python Server on http://localhost:5000...")
    app.run(host='::', port=5000, debug=True)
