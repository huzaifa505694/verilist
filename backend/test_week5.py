import os
import sys
import unittest
import json

# Ensure project root is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app, _rate_limit_store
import backend.models as models
from backend.ai_models.estimator import PriceEstimator
from backend.ai_models.detector import analyze_listing

class VeriListWeek5TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app.test_client()
        cls.app.testing = True

        # Register/Login a seller to use for testing
        cls.seller_credentials = {
            'email': 'seller5@gmail.com',
            'password': 'password123'
        }
        
        _rate_limit_store.clear()
        
        # Check if user already exists, else register
        user = models.get_user_by_email(cls.seller_credentials['email'])
        if not user:
            pwd_hash = models.hash_password(cls.seller_credentials['password'])
            models.create_user(cls.seller_credentials['email'], pwd_hash, "Week 5 Seller", "SELLER")
            
        # Log in to get token
        response = cls.app.post('/api/auth/login', 
                                 data=json.dumps(cls.seller_credentials),
                                 content_type='application/json')
        data = json.loads(response.data.decode('utf-8'))
        cls.seller_token = data.get('token')
        cls.app._cookies.clear()

    def setUp(self):
        _rate_limit_store.clear()
        self.app._cookies.clear()

    def _get_headers(self, token):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def test_01_estimator_price_prediction(self):
        """Test PriceEstimator.estimate_price with normal values"""
        pred, min_p, max_p = PriceEstimator.estimate_price(2018, "Toyota", "Camry", 50000, "GOOD")
        self.assertGreater(pred, 0)
        self.assertGreater(min_p, 0)
        self.assertGreater(max_p, min_p)
        self.assertEqual(pred, round(pred, -2)) # Rounded to nearest 100
        
    def test_02_estimator_edge_cases(self):
        """Test PriceEstimator edge cases like out-of-range values or unknown makes/models"""
        # Extremely high mileage, low year, unknown make/model
        pred, min_p, max_p = PriceEstimator.estimate_price(1990, "SuperRareCarBrand", "ModelX", 999999, "POOR")
        self.assertGreaterEqual(pred, 500.0) # Clamped to min of $500 or $1000
        self.assertGreaterEqual(min_p, 500.0)
        self.assertGreaterEqual(max_p, min_p)

    def test_03_detector_analysis(self):
        """Test analyze_listing detector flagging rules"""
        # Case A: Normal Listing
        res = analyze_listing(15000, 2018, "Toyota", "Camry", 50000, "GOOD", "A well maintained Camry.")
        self.assertEqual(res['status'], 'ACTIVE')
        self.assertGreaterEqual(res['trust_score'], 70)
        
        # Case B: Suspiciously Low Price (Should flag and status PENDING_REVIEW)
        res_scam = analyze_listing(1000, 2018, "Toyota", "Camry", 50000, "GOOD", "A well maintained Camry.")
        self.assertEqual(res_scam['status'], 'PENDING_REVIEW')
        self.assertIn("Suspiciously Low Price (Potential Scam)", res_scam['risk_flags'])
        self.assertLess(res_scam['trust_score'], 70)

        # Case C: Scam description words
        res_desc = analyze_listing(15000, 2018, "Toyota", "Camry", 50000, "GOOD", "Please pay using wire transfer or western union.")
        self.assertEqual(res_desc['status'], 'PENDING_REVIEW')
        self.assertIn("Suspicious Payment terms in Description", res_desc['risk_flags'])

    def test_04_predict_price_endpoint(self):
        """Test POST /predict-price live prediction API endpoint"""
        payload = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2018,
            "mileage": 50000,
            "condition": "GOOD"
        }
        response = self.app.post('/predict-price', data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('predicted_price', data)
        self.assertIn('range', data)
        self.assertIn('feature_importance', data)
        self.assertEqual(len(data['range']), 2)

    def test_05_predict_price_endpoint_missing_fields(self):
        """Test POST /predict-price with missing fields (should return 400)"""
        payload = {
            "make": "Toyota",
            "model": "Camry"
            # year, mileage, condition are missing
        }
        response = self.app.post('/predict-price', data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 400)

    def test_06_model_metrics_endpoint(self):
        """Test GET /api/ai/model-metrics performance metrics endpoint"""
        response = self.app.get('/api/ai/model-metrics')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('model_loaded', data)
        if data['model_loaded']:
            self.assertIn('r2', data)
            self.assertIn('mae', data)
            self.assertIn('feature_importances', data)

    def test_07_listing_creation_caching(self):
        """Test that creating a listing caches the price prediction"""
        headers = self._get_headers(self.seller_token)
        payload = {
            "title": "2018 Ford Explorer Sport",
            "description": "Very nice SUV. Runs clean, minor scratches on bumper.",
            "price": 22000.00,
            "category": "VEHICLES",
            "make": "Ford",
            "model": "Explorer",
            "year": 2018,
            "mileage": 60000,
            "condition": "GOOD"
        }
        response = self.app.post('/api/listings', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data.decode('utf-8'))
        listing_id = data['listing']['id']
        
        # Verify prediction is cached in database
        prediction = models.get_price_prediction(listing_id)
        self.assertIsNotNone(prediction)
        self.assertIn('predicted_price', prediction)
        self.assertIn('predicted_price_min', prediction)
        self.assertIn('predicted_price_max', prediction)
        self.assertIn('feature_importance', prediction)

        # Verify fetching listing detail returns the cached price prediction
        detail_response = self.app.get(f'/api/listings/{listing_id}')
        self.assertEqual(detail_response.status_code, 200)
        detail_data = json.loads(detail_response.data.decode('utf-8'))
        self.assertIn('price_prediction', detail_data)
        self.assertEqual(detail_data['price_prediction']['predicted_price'], prediction['predicted_price'])

    def test_08_listing_creation_parts_category(self):
        """Test creating a listing under PARTS category where vehicle fields are missing/None"""
        headers = self._get_headers(self.seller_token)
        payload = {
            "title": "Toyota Camry Brake Pads",
            "description": "Brand new ceramic brake pads for front wheels. Never used, still in original box.",
            "price": 45.00,
            "category": "PARTS",
            "make": None,
            "model": None,
            "year": None,
            "mileage": None,
            "condition": None
        }
        response = self.app.post('/api/listings', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_09_electronics_prediction_and_caching(self):
        """Test estimating price and caching predictions for ELECTRONICS category"""
        headers = self._get_headers(self.seller_token)
        
        # Test /predict-price endpoint for electronics
        predict_payload = {
            "category": "ELECTRONICS",
            "make": "Apple",
            "model": "iPhone 14 Pro",
            "condition": "EXCELLENT"
        }
        predict_response = self.app.post('/predict-price', data=json.dumps(predict_payload), headers=headers)
        self.assertEqual(predict_response.status_code, 200)
        predict_data = json.loads(predict_response.data.decode('utf-8'))
        self.assertIn('predicted_price', predict_data)
        self.assertIn('range', predict_data)
        self.assertIsNotNone(predict_data['predicted_price'])
        
        # Test creating a listing under ELECTRONICS category
        create_payload = {
            "title": "Apple iPhone 14 Pro 128GB",
            "description": "Mint condition iPhone 14 Pro. No scratches, works perfectly, includes box and cable.",
            "price": 600.00,
            "category": "ELECTRONICS",
            "make": "Apple",
            "model": "iPhone 14 Pro",
            "year": None,
            "mileage": None,
            "condition": "EXCELLENT"
        }
        create_response = self.app.post('/api/listings', data=json.dumps(create_payload), headers=headers)
        self.assertEqual(create_response.status_code, 201)
        create_data = json.loads(create_response.data.decode('utf-8'))
        self.assertIn('listing', create_data)
        listing_id = create_data['listing']['id']
        
        # Verify fetching listing detail returns the cached price prediction
        detail_response = self.app.get(f'/api/listings/{listing_id}')
        self.assertEqual(detail_response.status_code, 200)
        detail_data = json.loads(detail_response.data.decode('utf-8'))
        self.assertIn('price_prediction', detail_data)
        self.assertIsNotNone(detail_data['price_prediction']['predicted_price'])

if __name__ == '__main__':
    unittest.main()
