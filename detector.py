import re
from backend.ai_models.estimator import PriceEstimator

SCAM_KEYWORDS = [
    r'wire\s+transfer',
    r'western\s+union',
    r'moneygram',
    r'gift\s+card',
    r'certified\s+check',
    r'prepay',
    r'shipper',
    r'no\s+in\s+person',
    r'cashier\'s\s+check'
]

def scan_text_for_scams(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    for pattern in SCAM_KEYWORDS:
        if re.search(pattern, text_lower):
            return True
    return False

def check_for_contact_info(text: str) -> bool:
    if not text:
        return False
    # Check for email pattern
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    # Check for US phone number pattern (basic check)
    phone_pattern = r'\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b'
    
    if re.search(email_pattern, text) or re.search(phone_pattern, text):
        return True
    return False

def analyze_listing(price: float, year: int, make: str, model: str, mileage: int, condition: str, description: str) -> dict:
    """
    Analyzes listing data for pricing anomalies, mileage anomalies, and scam text patterns.
    
    Returns:
        {
            'trust_score': int (0-100),
            'risk_flags': list of strings,
            'predicted_price_min': float,
            'predicted_price_max': float,
            'status': 'ACTIVE' or 'PENDING_REVIEW'
        }
    """
    # 1. Get fair price estimate range
    pred_price, pred_min, pred_max = PriceEstimator.estimate_price(year, make, model, mileage, condition)
    
    risk_flags = []
    trust_score = 100
    
    # 2. Check Price Deviation (Suspiciously Low Price)
    if price < (0.7 * pred_min):
        risk_flags.append("Suspiciously Low Price (Potential Scam)")
        trust_score -= 40
    elif price > (1.4 * pred_max):
        risk_flags.append("Inflated Asking Price")
        trust_score -= 15
        
    # 3. Check Mileage-Age Anomaly (Odometer Rollback check)
    current_year = 2026
    age = current_year - int(year)
    if age > 2:
        miles_per_year = float(mileage) / age
        if miles_per_year < 800:
            risk_flags.append("Anomaly: Unusually Low Mileage for Age (Odometer Check)")
            trust_score -= 30
            
    # 4. Check description text for payment scam terms
    if scan_text_for_scams(description):
        risk_flags.append("Suspicious Payment terms in Description")
        trust_score -= 40
        
    # 5. Check description for contact info bypass
    if check_for_contact_info(description):
        risk_flags.append("Bypass Attempt: Contact details in description")
        trust_score -= 15
        
    # Ensure trust score doesn't drop below 0
    trust_score = max(0, trust_score)
    
    # Determine listing status based on trust score threshold
    # If trust score is low (< 70), send to admin review queue
    status = 'PENDING_REVIEW' if trust_score < 70 else 'ACTIVE'
    
    return {
        'trust_score': trust_score,
        'risk_flags': risk_flags,
        'predicted_price_min': pred_min,
        'predicted_price_max': pred_max,
        'status': status
    }
