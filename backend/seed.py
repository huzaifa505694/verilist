import random
import uuid
import json
import os
from backend.firebase_db import get_firestore_db
import backend.models as models
from backend.ai_models.detector import analyze_listing

FIRST_NAMES = ['Liam', 'Olivia', 'Noah', 'Emma', 'Oliver', 'Ava', 'Elijah', 'Charlotte', 'William', 'Sophia', 
               'James', 'Amelia', 'Benjamin', 'Isabella', 'Lucas', 'Mia', 'Henry', 'Evelyn', 'Alexander', 'Harper']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 
              'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']

CAR_MODELS = {
    'Toyota': ['Camry', 'Corolla', 'RAV4', 'Prius', 'Highlander', 'Tacoma'],
    'Honda': ['Civic', 'Accord', 'CR-V', 'Pilot', 'Odyssey', 'Fit'],
    'Ford': ['F-150', 'Mustang', 'Explorer', 'Focus', 'Escape', 'Fusion'],
    'Chevrolet': ['Silverado', 'Camaro', 'Equinox', 'Malibu', 'Tahoe', 'Cruze'],
    'Tesla': ['Model 3', 'Model Y', 'Model S', 'Model X'],
    'BMW': ['3 Series', '5 Series', 'X5', 'X3', '328i'],
    'Audi': ['A4', 'A6', 'Q5', 'Q7'],
    'Mercedes': ['C-Class', 'E-Class', 'GLE', 'GLC']
}

CONDITIONS = ['EXCELLENT', 'GOOD', 'FAIR', 'POOR']

def generate_random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def clear_collection(db, collection_name):
    print(f"Clearing collection: {collection_name}...")
    docs = db.collection(collection_name).stream()
    batch = db.batch()
    count = 0
    for doc in docs:
        batch.delete(doc.reference)
        count += 1
        if count >= 400: # Firestore limit is 500 per batch
            batch.commit()
            batch = db.batch()
            count = 0
    if count > 0:
        batch.commit()

def run_seed():
    print("Connecting to Firestore database...")
    db = get_firestore_db()
    
    print("Clearing existing NoSQL collections...")
    clear_collection(db, 'offers')
    clear_collection(db, 'saved_listings')
    clear_collection(db, 'listings')
    clear_collection(db, 'reviews')
    clear_collection(db, 'notifications')
    clear_collection(db, 'users')
    
    print("Seeding users...")
    pwd_hash = models.hash_password("password123")
    
    # Create default accounts for testing
    admin = models.create_user("admin@gmail.com", pwd_hash, "Admin User", "ADMIN")
    seller = models.create_user("seller@gmail.com", pwd_hash, "John Seller", "SELLER")
    buyer = models.create_user("buyer@gmail.com", pwd_hash, "Jane Buyer", "BUYER")
    
    sellers = [seller]
    buyers = [buyer]
    
    emails_seen = {"admin@gmail.com", "seller@gmail.com", "buyer@gmail.com"}
    
    # Create 35 random users
    for _ in range(35):
        while True:
            name = generate_random_name()
            email = f"{name.replace(' ', '.').lower()}{random.randint(10,99)}@gmail.com"
            if email not in emails_seen:
                emails_seen.add(email)
                break
        
        role_rand = random.random()
        if role_rand > 0.7:
            role = 'SELLER'
        elif role_rand > 0.95:
            role = 'ADMIN'
        else:
            role = 'BUYER'
            
        user = models.create_user(email, pwd_hash, name, role)
        if role == 'SELLER':
            sellers.append(user)
        elif role == 'BUYER':
            buyers.append(user)
            
    print(f"Users seeded. Total sellers: {len(sellers)}, buyers: {len(buyers)}.")
    
    print("Seeding 100 listings to Firestore...")
    makes = list(CAR_MODELS.keys())
    
    for i in range(100):
        make = random.choice(makes)
        model = random.choice(CAR_MODELS[make])
        year = random.randint(2010, 2026)
        
        # Mileage formula based on age
        years_old = 2026 - year
        avg_mileage_per_year = random.randint(8000, 15000)
        calculated_mileage = max(0, int(years_old * avg_mileage_per_year + random.randint(-5000, 5000)))
        mileage = random.randint(100, 3000) if year == 2026 else calculated_mileage
        
        condition = random.choice(CONDITIONS)
        
        # Dynamic base original price estimation
        original_val = 35000.0
        if make in ['Tesla', 'BMW', 'Audi', 'Mercedes']:
            original_val = 55000.0
        elif make in ['Ford', 'Chevrolet'] and model in ['F-150', 'Silverado', 'Tahoe']:
            original_val = 48000.0
            
        # Price depreciation
        price = original_val - (years_old * (original_val * 0.08)) - (mileage * 0.12)
        
        # Condition adjustment
        if condition == 'EXCELLENT':
            price *= 1.1
        elif condition == 'GOOD':
            price *= 0.95
        elif condition == 'FAIR':
            price *= 0.75
        elif condition == 'POOR':
            price *= 0.5
            
        # Random price noise
        price *= random.uniform(0.9, 1.1)
        price = max(1000.0, round(price / 100) * 100)
        
        # Introduce anomalous pricing or description in 15% of listings to test the review queue
        is_scam = random.random() < 0.15
        if is_scam:
            scam_type = random.choice(['low_price', 'bad_desc', 'low_mileage'])
            if scam_type == 'low_price':
                price = round(price * 0.35, -2)
                description = f"Selling my {year} {make} {model} quickly. Moving out of country, must sell this week. Cash or bank check only."
            elif scam_type == 'bad_desc':
                description = f"Beautiful {year} {make} {model} in great condition. Can ship it to you. Please prepay via certified check or wire transfer."
            else: # low_mileage rollback
                mileage = 1200
                description = f"Selling my pristine {year} {make} {model} with extremely low mileage. Garaged its entire life, clean title."
        else:
            description = f"This {condition.lower()} condition {year} {make} {model} features {mileage:,} miles, standard equipment, clean title, and is priced to sell. Contact for more details."
            
        title = f"{year} {make} {model}"
        seller_user = random.choice(sellers)
        
        # Run anomaly detection
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
            'category': 'VEHICLES',
            'status': analysis['status'],
            'seller_id': seller_user['id'],
            'trust_score': analysis['trust_score'],
            'predicted_price_min': analysis['predicted_price_min'],
            'predicted_price_max': analysis['predicted_price_max'],
            'risk_flags': analysis['risk_flags']
        }
        
        models.create_listing(listing_data)
        
    print("Seeding reviews...")
    # Seed reviews for the default seller (John Seller)
    review_comments = [
        ("Great seller, very responsive and clean transaction.", 5),
        ("Car was exactly as described. Clean title, good negotiation.", 4),
        ("Had some minor delay in meetup but seller is honest.", 4),
        ("Trustworthy seller. The pricing was verified by AI, which gave me peace of mind.", 5)
    ]
    for comment, rating in review_comments:
        buyer_u = random.choice(buyers)
        models.create_review(None, buyer_u['id'], seller['id'], rating, comment)

    print("Seeding offers...")
    # Find active listings owned by John Seller
    john_listings = models.get_listings({'seller_id': seller['id'], 'status': 'ACTIVE'})
    if john_listings:
        # Create a couple of pending offers from a random buyer
        buyer_u = random.choice(buyers)
        models.create_offer(john_listings[0]['id'], buyer_u['id'], john_listings[0]['price'] * 0.9)
        if len(john_listings) > 1:
            buyer_u2 = random.choice(buyers)
            models.create_offer(john_listings[1]['id'], buyer_u2['id'], john_listings[1]['price'] * 0.85)
        
    print("Seeding notifications...")
    # Seed notifications for default seller and default buyer
    notifs = [
        (seller['id'], "New Offer Received", "You received a new offer of $12,500.00 on your 2015 Honda Accord.", "OFFER_RECEIVED"),
        (seller['id'], "Listing Approved", "Your listing for the 2018 Toyota Camry has been approved by the administrator.", "SYSTEM"),
        (buyer['id'], "Offer Accepted", "Your offer of $14,000.00 on the 2019 Ford Mustang has been accepted by the seller.", "OFFER_ACCEPTED"),
        (buyer['id'], "Welcome to VeriList!", "Thank you for joining VeriList! Get started by searching verified vehicles in our browse page.", "SYSTEM")
    ]
    for uid, title, msg, type_ in notifs:
        models.create_notification(uid, title, msg, type_)

    print("Firebase Firestore database seeded successfully.")

if __name__ == '__main__':
    run_seed()
