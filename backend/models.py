import bcrypt
import jwt
import datetime
import uuid
import json
from backend.firebase_db import get_firestore_db
from firebase_admin import firestore

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

# User Queries (Firestore)
def get_user_by_email(email: str):
    db = get_firestore_db()
    users_ref = db.collection('users')
    query = users_ref.where('email', '==', email.lower()).limit(1).stream()
    for doc in query:
        user_data = doc.to_dict()
        user_data['id'] = doc.id
        return user_data
    return None

def get_user_by_id(user_id: str):
    db = get_firestore_db()
    doc_ref = db.collection('users').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        user_data = doc.to_dict()
        user_data['id'] = doc.id
        return user_data
    return None

def create_user(email: str, password_hash: str, name: str, role: str) -> dict:
    user_id = str(uuid.uuid4())
    db = get_firestore_db()
    doc_ref = db.collection('users').document(user_id)
    user_data = {
        'email': email.lower(),
        'password_hash': password_hash,
        'name': name,
        'role': role,
        'created_at': datetime.datetime.utcnow().isoformat(),
        'updated_at': datetime.datetime.utcnow().isoformat()
    }
    doc_ref.set(user_data)
    
    res = {
        'id': user_id,
        'email': user_data['email'],
        'name': user_data['name'],
        'role': user_data['role']
    }
    return res

def update_user_role(user_id: str, role: str) -> bool:
    db = get_firestore_db()
    doc_ref = db.collection('users').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({
            'role': role,
            'updated_at': datetime.datetime.utcnow().isoformat()
        })
        return True
    return False

def get_all_users() -> list:
    db = get_firestore_db()
    users = []
    docs = db.collection('users').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
    for doc in docs:
        u = doc.to_dict()
        u['id'] = doc.id
        users.append(u)
    return users

# Listing Queries (Firestore)
def create_listing(listing_data: dict) -> dict:
    listing_id = str(uuid.uuid4())
    db = get_firestore_db()
    doc_ref = db.collection('listings').document(listing_id)
    data = {
        'title': listing_data['title'],
        'description': listing_data['description'],
        'price': float(listing_data['price']),
        'make': listing_data['make'],
        'model': listing_data['model'],
        'year': int(listing_data['year']) if listing_data.get('year') is not None else None,
        'mileage': int(listing_data['mileage']) if listing_data.get('mileage') is not None else None,
        'condition': listing_data['condition'],
        'category': listing_data['category'],
        'status': listing_data.get('status', 'ACTIVE'),
        'seller_id': listing_data['seller_id'],
        'trust_score': int(listing_data.get('trust_score', 100)),
        'predicted_price_min': float(listing_data['predicted_price_min']) if listing_data.get('predicted_price_min') is not None else None,
        'predicted_price_max': float(listing_data['predicted_price_max']) if listing_data.get('predicted_price_max') is not None else None,
        'risk_flags': listing_data.get('risk_flags', []),
        'views': 0,
        'price_history': [{'price': float(listing_data['price']), 'date': datetime.datetime.utcnow().isoformat()}],
        'created_at': datetime.datetime.utcnow().isoformat(),
        'updated_at': datetime.datetime.utcnow().isoformat()
    }
    doc_ref.set(data)
    
    data['id'] = listing_id
    return data

def get_listings(filters: dict = None, return_total: bool = False) -> list:
    db = get_firestore_db()
    listings_ref = db.collection('listings')
    
    # Base filter by status (ACTIVE by default)
    req_status = 'ACTIVE'
    if filters and 'status' in filters:
        req_status = filters['status']
        
    if req_status:
        query = listings_ref.where('status', '==', req_status)
    else:
        query = listings_ref
        
    docs = query.stream()
    listings = []
    
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        
        # In-memory filter processing to prevent composite index requirement
        if filters:
            if 'category' in filters and filters['category'] and d.get('category') != filters['category']:
                continue
            if 'make' in filters and filters['make'] and d.get('make', '').lower() != filters['make'].lower():
                continue
            if 'model' in filters and filters['model'] and d.get('model', '').lower() != filters['model'].lower():
                continue
            if 'condition' in filters and filters['condition'] and d.get('condition', '').upper() != filters['condition'].upper():
                continue
            if 'year_min' in filters and filters['year_min'] and d.get('year', 0) < int(filters['year_min']):
                continue
            if 'year_max' in filters and filters['year_max'] and d.get('year', 0) > int(filters['year_max']):
                continue
            if 'price_min' in filters and filters['price_min'] and d.get('price', 0.0) < float(filters['price_min']):
                continue
            if 'price_max' in filters and filters['price_max'] and d.get('price', 0.0) > float(filters['price_max']):
                continue
            if 'seller_id' in filters and filters['seller_id'] and d.get('seller_id') != filters['seller_id']:
                continue
            if 'search' in filters and filters['search']:
                search_term = filters['search'].lower()
                title_match = search_term in d.get('title', '').lower()
                desc_match = search_term in d.get('description', '').lower()
                if not (title_match or desc_match):
                    continue
                    
        listings.append(d)
        
    # Order by created_at descending
    listings.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    total_count = len(listings)
    
    # Page pagination offsets
    if filters:
        limit = filters.get('limit')
        offset = filters.get('offset')
        if offset is not None:
            listings = listings[offset:]
        if limit is not None:
            listings = listings[:limit]
            
    # Join seller metadata only for the final sliced listings
    seller_cache = {}
    for d in listings:
        seller_id = d.get('seller_id')
        if seller_id:
            if seller_id not in seller_cache:
                seller = get_user_by_id(seller_id)
                if seller:
                    seller_cache[seller_id] = {
                        'name': seller.get('name', 'Unknown'),
                        'email': seller.get('email', '')
                    }
                else:
                    seller_cache[seller_id] = {
                        'name': 'Unknown',
                        'email': ''
                    }
            s_data = seller_cache[seller_id]
            d['seller_name'] = s_data['name']
            d['seller_email'] = s_data['email']
        else:
            d['seller_name'] = 'Unknown'
            d['seller_email'] = ''
            
    if return_total:
        return listings, total_count
    return listings

def get_listing_by_id(listing_id: str, increment_view: bool = False):
    db = get_firestore_db()
    doc_ref = db.collection('listings').document(listing_id)
    doc = doc_ref.get()
    if doc.exists:
        d = doc.to_dict()
        d['id'] = doc.id
        
        if increment_view:
            try:
                new_views = d.get('views', 0) + 1
                doc_ref.update({'views': new_views})
                d['views'] = new_views
            except Exception:
                pass
        
        seller = get_user_by_id(d['seller_id'])
        if seller:
            d['seller_name'] = seller.get('name', 'Unknown')
            d['seller_email'] = seller.get('email', '')
        else:
            d['seller_name'] = 'Unknown'
            d['seller_email'] = ''
        return d
    return None

def update_listing_status(listing_id: str, status: str) -> bool:
    db = get_firestore_db()
    doc_ref = db.collection('listings').document(listing_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({
            'status': status,
            'updated_at': datetime.datetime.utcnow().isoformat()
        })
        return True
    return False

def update_listing(listing_id: str, update_data: dict) -> bool:
    db = get_firestore_db()
    doc_ref = db.collection('listings').document(listing_id)
    doc = doc_ref.get()
    if doc.exists:
        current_listing = doc.to_dict()
        fields = ['title', 'description', 'price', 'make', 'model', 'year', 'mileage', 'condition', 'category', 'status', 'trust_score', 'predicted_price_min', 'predicted_price_max', 'risk_flags']
        data = {}
        for f in fields:
            if f in update_data:
                if f == 'price':
                    data[f] = float(update_data[f])
                elif f in ('year', 'mileage', 'trust_score'):
                    data[f] = int(update_data[f]) if update_data[f] is not None else None
                else:
                    data[f] = update_data[f]
        
        # Track price history changes
        if 'price' in update_data:
            new_price = float(update_data['price'])
            old_price = float(current_listing.get('price', 0))
            if new_price != old_price:
                history_event = {'price': new_price, 'date': datetime.datetime.utcnow().isoformat()}
                data['price_history'] = firestore.ArrayUnion([history_event])
                
        data['updated_at'] = datetime.datetime.utcnow().isoformat()
        doc_ref.update(data)
        return True
    return False

def delete_listing(listing_id: str) -> bool:
    db = get_firestore_db()
    doc_ref = db.collection('listings').document(listing_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({
            'status': 'REMOVED',
            'updated_at': datetime.datetime.utcnow().isoformat()
        })
        return True
    return False

# Saved Listings (Firestore)
def toggle_saved_listing(user_id: str, listing_id: str) -> str:
    db = get_firestore_db()
    saved_ref = db.collection('saved_listings')
    query = saved_ref.where('user_id', '==', user_id).where('listing_id', '==', listing_id).limit(1).stream()
    
    existing_doc_id = None
    for doc in query:
        existing_doc_id = doc.id
        break
        
    if existing_doc_id:
        saved_ref.document(existing_doc_id).delete()
        return 'unsaved'
    else:
        doc_id = f"{user_id}_{listing_id}"
        saved_ref.document(doc_id).set({
            'user_id': user_id,
            'listing_id': listing_id,
            'created_at': datetime.datetime.utcnow().isoformat()
        })
        return 'saved'

def get_saved_listings_for_user(user_id: str) -> list:
    db = get_firestore_db()
    saved_ref = db.collection('saved_listings')
    query = saved_ref.where('user_id', '==', user_id).stream()
    
    listings = []
    for doc in query:
        item = doc.to_dict()
        listing_data = get_listing_by_id(item['listing_id'])
        if listing_data:
            listings.append(listing_data)
    return listings

# Offers Queries (Firestore)
def create_offer(listing_id: str, buyer_id: str, amount: float) -> dict:
    offer_id = str(uuid.uuid4())
    db = get_firestore_db()
    doc_ref = db.collection('offers').document(offer_id)
    data = {
        'id': offer_id,
        'listing_id': listing_id,
        'buyer_id': buyer_id,
        'amount': float(amount),
        'status': 'PENDING',
        'created_at': datetime.datetime.utcnow().isoformat()
    }
    doc_ref.set({k: v for k, v in data.items() if k != 'id'})
    return data

def get_offers_for_user(user_id: str, role: str) -> list:
    db = get_firestore_db()
    offers_ref = db.collection('offers')
    user_cache = {}
    all_offers = []
    
    if role == 'SELLER':
        # 1. Fetch seller's listings first to get matching listing_ids
        seller_listings_docs = db.collection('listings').where('seller_id', '==', user_id).stream()
        listing_map = {}
        for l_doc in seller_listings_docs:
            ld = l_doc.to_dict()
            listing_map[l_doc.id] = ld
            
        if not listing_map:
            return []

        listing_ids = list(listing_map.keys())

        # 2. Batch query offers by listing_id in chunks of 30
        offer_docs = []
        for i in range(0, len(listing_ids), 30):
            chunk = listing_ids[i:i+30]
            docs = offers_ref.where('listing_id', 'in', chunk).stream()
            offer_docs.extend(docs)

        # 3. Batch fetch buyer user names
        buyer_ids = set()
        raw_offers = []
        for doc in offer_docs:
            o = doc.to_dict()
            o['id'] = doc.id
            raw_offers.append(o)
            if o.get('buyer_id'):
                buyer_ids.add(o.get('buyer_id'))

        buyer_ids_list = list(buyer_ids)
        if buyer_ids_list:
            u_refs = [db.collection('users').document(uid) for uid in buyer_ids_list]
            u_docs = db.get_all(u_refs)
            for udoc in u_docs:
                if udoc.exists:
                    u_data = udoc.to_dict()
                    user_cache[udoc.id] = u_data.get('name', 'Unknown')

        for o in raw_offers:
            l_data = listing_map.get(o.get('listing_id'))
            if not l_data:
                continue
            o['listing_title'] = l_data.get('title', 'Unknown')
            o['listing_price'] = l_data.get('price', 0.0)
            b_id = o.get('buyer_id')
            o['buyer_name'] = user_cache.get(b_id, 'Unknown') if b_id else 'Unknown'
            all_offers.append(o)

    elif role == 'BUYER':
        # 1. Query offers for this buyer
        docs = offers_ref.where('buyer_id', '==', user_id).stream()
        raw_offers = []
        listing_ids = set()
        for doc in docs:
            o = doc.to_dict()
            o['id'] = doc.id
            raw_offers.append(o)
            if o.get('listing_id'):
                listing_ids.add(o.get('listing_id'))

        if not raw_offers:
            return []

        # 2. Batch fetch listings using db.get_all()
        listing_map = {}
        seller_ids = set()
        listing_ids_list = list(listing_ids)
        if listing_ids_list:
            l_refs = [db.collection('listings').document(lid) for lid in listing_ids_list]
            l_docs = db.get_all(l_refs)
            for ldoc in l_docs:
                if ldoc.exists:
                    ld = ldoc.to_dict()
                    listing_map[ldoc.id] = ld
                    if ld.get('seller_id'):
                        seller_ids.add(ld.get('seller_id'))

        # 3. Batch fetch seller names using db.get_all()
        seller_ids_list = list(seller_ids)
        if seller_ids_list:
            u_refs = [db.collection('users').document(uid) for uid in seller_ids_list]
            u_docs = db.get_all(u_refs)
            for udoc in u_docs:
                if udoc.exists:
                    u_data = udoc.to_dict()
                    user_cache[udoc.id] = u_data.get('name', 'Unknown')

        for o in raw_offers:
            l_data = listing_map.get(o.get('listing_id'))
            if not l_data:
                # If listing metadata unavailable, keep basic offer info
                o['listing_title'] = 'Listing'
                o['listing_price'] = o.get('amount', 0.0)
                o['seller_name'] = 'Seller'
            else:
                o['listing_title'] = l_data.get('title', 'Unknown')
                o['listing_price'] = l_data.get('price', 0.0)
                s_id = l_data.get('seller_id')
                o['seller_name'] = user_cache.get(s_id, 'Unknown') if s_id else 'Unknown'
            all_offers.append(o)

    else: # ADMIN
        docs = offers_ref.stream()
        listing_cache = {}
        for doc in docs:
            o = doc.to_dict()
            o['id'] = doc.id
            listing_id = o.get('listing_id')
            if not listing_id:
                continue
            if listing_id not in listing_cache:
                l_doc = db.collection('listings').document(listing_id).get()
                listing_cache[listing_id] = l_doc.to_dict() if l_doc.exists else None
            listing = listing_cache[listing_id]
            if not listing:
                continue
            o['listing_title'] = listing.get('title', 'Unknown')
            o['listing_price'] = listing.get('price', 0.0)
            o['seller_name'] = 'Unknown'
            o['buyer_name'] = 'Unknown'
            all_offers.append(o)

    all_offers.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return all_offers

def update_offer_status(offer_id: str, status: str) -> bool:
    db = get_firestore_db()
    doc_ref = db.collection('offers').document(offer_id)
    doc_ref.update({
        'status': status
    })
    return True

def counter_offer(offer_id: str, counter_amount: float, last_action_by: str) -> bool:
    db = get_firestore_db()
    doc_ref = db.collection('offers').document(offer_id)
    doc_ref.update({
        'status': 'COUNTER_OFFER',
        'counter_amount': float(counter_amount),
        'last_action_by': last_action_by
    })
    return True

# Review Queries (Firestore)
def create_review(listing_id: str, reviewer_id: str, seller_id: str, rating: int, comment: str) -> dict:
    review_id = str(uuid.uuid4())
    db = get_firestore_db()
    doc_ref = db.collection('reviews').document(review_id)
    data = {
        'listing_id': listing_id,
        'reviewer_id': reviewer_id,
        'seller_id': seller_id,
        'rating': int(rating),
        'comment': comment,
        'created_at': datetime.datetime.utcnow().isoformat()
    }
    doc_ref.set(data)
    
    # Recalculate average star rating dynamically for the seller
    try:
        reviews_query = db.collection('reviews').where('seller_id', '==', seller_id).stream()
        all_ratings = [r.to_dict().get('rating', 0) for r in reviews_query]
        if all_ratings:
            avg_rating = sum(all_ratings) / len(all_ratings)
            db.collection('users').document(seller_id).update({
                'average_rating': round(avg_rating, 2),
                'total_reviews': len(all_ratings)
            })
    except Exception as e:
        print(f"Error updating dynamic seller ratings: {str(e)}")
        
    reviewer = get_user_by_id(reviewer_id)
    res = doc_ref.get().to_dict()
    res['id'] = review_id
    res['reviewer_name'] = reviewer.get('name', 'Unknown') if reviewer else 'Unknown'
    return res

def get_reviews_for_seller(seller_id: str) -> list:
    db = get_firestore_db()
    reviews_ref = db.collection('reviews')
    query = reviews_ref.where('seller_id', '==', seller_id).stream()
    
    reviews = []
    reviewer_cache = {}
    for doc in query:
        r = doc.to_dict()
        r['id'] = doc.id
        reviewer_id = r.get('reviewer_id')
        if reviewer_id:
            if reviewer_id not in reviewer_cache:
                reviewer = get_user_by_id(reviewer_id)
                reviewer_cache[reviewer_id] = reviewer.get('name', 'Unknown') if reviewer else 'Unknown'
            r['reviewer_name'] = reviewer_cache[reviewer_id]
        else:
            r['reviewer_name'] = 'Unknown'
        reviews.append(r)
        
    reviews.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return reviews

# Notification Queries (Firestore)
def create_notification(user_id: str, title: str, message: str, type_: str = 'SYSTEM') -> dict:
    notif_id = str(uuid.uuid4())
    db = get_firestore_db()
    doc_ref = db.collection('notifications').document(notif_id)
    data = {
        'id': notif_id,
        'user_id': user_id,
        'title': title,
        'message': message,
        'type': type_,
        'is_read': 0,
        'created_at': datetime.datetime.utcnow().isoformat()
    }
    doc_ref.set({k: v for k, v in data.items() if k != 'id'})
    return data

def get_notifications_for_user(user_id: str, only_unread: bool = False) -> list:
    db = get_firestore_db()
    notifs_ref = db.collection('notifications')
    query = notifs_ref.where('user_id', '==', user_id)
    if only_unread:
        query = query.where('is_read', '==', 0)
        
    docs = query.stream()
    notifs = []
    for doc in docs:
        n = doc.to_dict()
        n['id'] = doc.id
        notifs.append(n)
        
    notifs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return notifs

def mark_notification_as_read(notification_id: str, user_id: str) -> bool:
    db = get_firestore_db()
    doc_ref = db.collection('notifications').document(notification_id)
    doc = doc_ref.get()
    if doc.exists:
        n = doc.to_dict()
        if n['user_id'] == user_id:
            doc_ref.update({'is_read': 1})
            return True
    return False

def mark_all_notifications_as_read(user_id: str) -> bool:
    db = get_firestore_db()
    notifs_ref = db.collection('notifications')
    query = notifs_ref.where('user_id', '==', user_id).where('is_read', '==', 0).stream()
    
    count = 0
    for doc in query:
        notifs_ref.document(doc.id).update({'is_read': 1})
        count += 1
    return count > 0

# Admin Specific Queries
def get_all_listings_admin() -> list:
    return get_listings({'status': None})


# Price Predictions Cache (Week 5)
def get_price_prediction(listing_id: str) -> dict:
    db = get_firestore_db()
    doc_ref = db.collection('price_predictions').document(listing_id)
    doc = doc_ref.get()
    if doc.exists:
        d = doc.to_dict()
        d['listing_id'] = doc.id
        return d
    return None

def create_price_prediction(listing_id: str, predicted_price: float, min_price: float, max_price: float, feature_importance: dict) -> dict:
    db = get_firestore_db()
    doc_ref = db.collection('price_predictions').document(listing_id)
    data = {
        'predicted_price': float(predicted_price),
        'predicted_price_min': float(min_price),
        'predicted_price_max': float(max_price),
        'feature_importance': feature_importance,
        'calculated_at': datetime.datetime.utcnow().isoformat()
    }
    doc_ref.set(data)
    data['listing_id'] = listing_id
    return data
