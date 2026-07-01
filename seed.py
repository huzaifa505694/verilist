import random
import uuid
import json
import os
from backend.db import get_db_connection, get_db_cursor, qp, init_db
from backend.models import hash_password, create_user
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

def run_seed():
    # Make sure DB is initialized
    print("Initializing database tables...")
    init_db()
    
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    
    print("Clearing existing data...")
    cursor.execute("DELETE FROM offers")
    cursor.execute("DELETE FROM saved_listings")
    cursor.execute("DELETE FROM listings")
    cursor.execute("DELETE FROM users")
    conn.commit()
    
    print("Seeding users...")
    pwd_hash = hash_password("password123")
    
    # Create default accounts for testing
    admin = create_user("admin@gmail.com", pwd_hash, "Admin User", "ADMIN")
    seller = create_user("seller@gmail.com", pwd_hash, "John Seller", "SELLER")
    buyer = create_user("buyer@gmail.com", pwd_hash, "Jane Buyer", "BUYER")
    
    sellers = [seller]
    buyers = [buyer]
    
    # Create 35 random users
    for _ in range(35):
        name = generate_random_name()
        email = f"{name.replace(' ', '.').lower()}{random.randint(10,99)}@gmail.com"
        
        role_rand = random.random()
        if role_rand > 0.7:
            role = 'SELLER'
        elif role_rand > 0.95:
            role = 'ADMIN'
        else:
            role = 'BUYER'
            
        user = create_user(email, pwd_hash, name, role)
        if role == 'SELLER':
            sellers.append(user)
        elif role == 'BUYER':
            buyers.append(user)
            
    print(f"Users seeded. Total sellers: {len(sellers)}, buyers: {len(buyers)}.")
    
    print("Seeding 100 listings...")
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
                # Priced 60% below normal
                price = round(price * 0.35, -2)
                description = f"Selling my {year} {make} {model} quickly. Moving out of country, must sell this week. Cash or bank check only."
            elif scam_type == 'bad_desc':
                description = f"Beautiful {year} {make} {model} in great condition. Can ship it to you. Please prepay via certified check or wire transfer."
            else: # low_mileage rollback
                mileage = 1200 # Extremely low for age
                description = f"Selling my pristine {year} {make} {model} with extremely low mileage. Garaged its entire life, clean title."
        else:
            description = f"This {condition.lower()} condition {year} {make} {model} features {mileage:,} miles, standard equipment, clean title, and is priced to sell. Contact for more details."
            
        title = f"{year} {make} {model}"
        seller = random.choice(sellers)
        
        # Run anomaly detection
        analysis = analyze_listing(price, year, make, model, mileage, condition, description)
        
        insert_query = qp('''
            INSERT INTO listings (
                id, title, description, price, make, model, year, mileage, condition, 
                category, status, seller_id, trust_score, predicted_price_min, 
                predicted_price_max, risk_flags
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''')
        
        cursor.execute(
            insert_query,
            (
                str(uuid.uuid4()),
                title,
                description,
                price,
                make,
                model,
                year,
                mileage,
                condition,
                'VEHICLES',
                analysis['status'],
                seller['id'],
                analysis['trust_score'],
                analysis['predicted_price_min'],
                analysis['predicted_price_max'],
                json.dumps(analysis['risk_flags'])
            )
        )
        
    conn.commit()
    conn.close()
    print("Database seeded with 100 listings and users successfully.")

if __name__ == '__main__':
    run_seed()
