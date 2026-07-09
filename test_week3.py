import os
import sys
import unittest
import json

# Ensure project root is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app, _rate_limit_store
import backend.models as models

class VeriListWeek3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app.test_client()
        cls.app.testing = True
        
        # Test Credentials
        cls.seller_credentials = {
            'email': 'seller@gmail.com',
            'password': 'password123'
        }
        cls.buyer_credentials = {
            'email': 'buyer@gmail.com',
            'password': 'password123'
        }
        cls.admin_credentials = {
            'email': 'admin@gmail.com',
            'password': 'password123'
        }
        
        # Clear rate limiter before fetching tokens
        _rate_limit_store.clear()
        
        # Log in users once to get tokens
        def get_auth_token(credentials):
            response = cls.app.post('/api/auth/login', 
                                     data=json.dumps(credentials),
                                     content_type='application/json')
            data = json.loads(response.data.decode('utf-8'))
            return data.get('token')
            
        cls.seller_token = get_auth_token(cls.seller_credentials)
        cls.buyer_token = get_auth_token(cls.buyer_credentials)
        cls.admin_token = get_auth_token(cls.admin_credentials)
        
        # Clear cookie jar so it doesn't pollute subsequent test requests
        cls.app._cookies.clear()
        
        # We will create a test listing to perform read, update, delete tests on
        cls.test_listing_id = None
        cls.test_seller_id = None

    def setUp(self):
        # Clear the rate limit store before every test run
        _rate_limit_store.clear()
        # Clear any stored cookies to force authorization via headers
        self.app._cookies.clear()

    def _get_headers(self, token):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    # ==========================================
    # 1. LISTINGS CRUD TESTS
    # ==========================================
    
    def test_01_create_listing_success(self):
        """Test successful listing creation (Seller) & Price History initialization"""
        headers = self._get_headers(self.seller_token)
        payload = {
            "title": "2019 Honda Accord Sport",
            "description": "Very clean family sedan. Runs and drives like new. Clean title in hand.",
            "price": 18500.00,
            "category": "VEHICLES",
            "make": "Honda",
            "model": "Accord",
            "year": 2019,
            "mileage": 45000,
            "condition": "EXCELLENT"
        }
        response = self.app.post('/api/listings', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('listing', data)
        self.assertIn('id', data['listing'])
        self.assertEqual(data['listing']['title'], payload['title'])
        self.assertEqual(data['listing']['price'], payload['price'])
        
        # Verify Price History Initialized
        self.assertIn('price_history', data['listing'])
        self.assertEqual(len(data['listing']['price_history']), 1)
        self.assertEqual(data['listing']['price_history'][0]['price'], payload['price'])
        
        # Cache listing ID and Seller ID for subsequent tests
        VeriListWeek3TestCase.test_listing_id = data['listing']['id']
        VeriListWeek3TestCase.test_seller_id = data['listing']['seller_id']

    def test_02_create_listing_validation_failures(self):
        """Test listing creation with invalid values (negative price, negative mileage, missing fields)"""
        headers = self._get_headers(self.seller_token)
        
        # Case A: Negative Price (should fail schema constraint min: 0.01)
        payload_neg_price = {
            "title": "Invalid Price Car",
            "description": "Testing negative price validation constraint.",
            "price": -500.00,
            "category": "VEHICLES",
            "make": "Ford",
            "model": "Mustang",
            "year": 2020,
            "mileage": 15000,
            "condition": "EXCELLENT"
        }
        response = self.app.post('/api/listings', data=json.dumps(payload_neg_price), headers=headers)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertFalse(data['success'])
        self.assertIn('validation_errors', data)
        self.assertIn('price', data['validation_errors'])

        # Case B: Negative Mileage (should fail category-specific validation)
        _rate_limit_store.clear()  # reset before next request
        payload_neg_mileage = {
            "title": "Invalid Mileage Car",
            "description": "Testing negative mileage validation constraint.",
            "price": 12000.00,
            "category": "VEHICLES",
            "make": "Ford",
            "model": "Mustang",
            "year": 2020,
            "mileage": -500,
            "condition": "EXCELLENT"
        }
        response = self.app.post('/api/listings', data=json.dumps(payload_neg_mileage), headers=headers)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertFalse(data['success'])
        self.assertIn('validation_errors', data)
        self.assertIn('mileage', data['validation_errors'])

        # Case C: Invalid Year range (e.g. 3000)
        _rate_limit_store.clear()
        payload_invalid_year = {
            "title": "Future Car",
            "description": "Testing year validation constraint.",
            "price": 12000.00,
            "category": "VEHICLES",
            "make": "Ford",
            "model": "Mustang",
            "year": 3000,
            "mileage": 100,
            "condition": "EXCELLENT"
        }
        response = self.app.post('/api/listings', data=json.dumps(payload_invalid_year), headers=headers)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('year', data['validation_errors'])

    def test_03_get_listings_with_filters_and_pagination(self):
        """Test GET /listings with category, price range, condition filters and pagination"""
        # A: Filter by Category and Condition
        response = self.app.get('/api/listings?category=VEHICLES&condition=EXCELLENT')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('listings', data)
        for listing in data['listings']:
            self.assertEqual(listing['category'], 'VEHICLES')
            self.assertEqual(listing['condition'], 'EXCELLENT')
            
        # B: Filter by Price Range
        response = self.app.get('/api/listings?price_min=10000&price_max=25000')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        for listing in data['listings']:
            self.assertTrue(10000 <= listing['price'] <= 25000)
            
        # C: Pagination checks (page 1, limit 3)
        response = self.app.get('/api/listings?page=1&limit=3')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(len(data['listings']), 3)
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['limit'], 3)

    def test_04_get_single_listing(self):
        """Test GET /listings/:id for single listing and similar recommendations"""
        lid = VeriListWeek3TestCase.test_listing_id
        if not lid:
            self.skipTest("No test listing created.")
            
        # Single success path
        response = self.app.get(f'/api/listings/{lid}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('listing', data)
        self.assertEqual(data['listing']['id'], lid)
        self.assertIn('similar_listings', data)
        
        # Failure path (404 not found)
        response = self.app.get('/api/listings/non-existent-id-12345')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('error', data)

    def test_05_update_listing(self):
        """Test PUT /listings/:id (Update only by owning seller or failure otherwise) & Price History change tracking"""
        lid = VeriListWeek3TestCase.test_listing_id
        if not lid:
            self.skipTest("No test listing created.")
            
        # A: Failure path (Attempt to edit by Buyer)
        headers_buyer = self._get_headers(self.buyer_token)
        payload = {
            "title": "Hijacked Listing Title",
            "description": "Attempting to hijack a seller's listing using a buyer's token.",
            "price": 100.00,
            "category": "VEHICLES",
            "make": "Honda",
            "model": "Accord",
            "year": 2019,
            "mileage": 45000,
            "condition": "EXCELLENT"
        }
        response = self.app.put(f'/api/listings/{lid}', data=json.dumps(payload), headers=headers_buyer)
        self.assertEqual(response.status_code, 403) # Forbidden
        
        # B: Success path (Update by Owner Seller)
        headers_seller = self._get_headers(self.seller_token)
        updated_payload = {
            "title": "2019 Honda Accord Sport - Updated Details",
            "description": "Fresh oil change, new brake pads installed. Excellent runner. Negotiable price.",
            "price": 17900.00,
            "category": "VEHICLES",
            "make": "Honda",
            "model": "Accord",
            "year": 2019,
            "mileage": 45500,
            "condition": "EXCELLENT"
        }
        response = self.app.put(f'/api/listings/{lid}', data=json.dumps(updated_payload), headers=headers_seller)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['listing']['title'], updated_payload['title'])
        self.assertEqual(data['listing']['price'], updated_payload['price'])
        
        # Verify price change appended to price_history
        self.assertIn('price_history', data['listing'])
        self.assertEqual(len(data['listing']['price_history']), 2)
        self.assertEqual(data['listing']['price_history'][1]['price'], updated_payload['price'])

    def test_06_delete_listing_soft(self):
        """Test DELETE /listings/:id performs soft-delete (status -> 'REMOVED')"""
        lid = VeriListWeek3TestCase.test_listing_id
        if not lid:
            self.skipTest("No test listing created.")
            
        # Delete by owning seller
        headers = self._get_headers(self.seller_token)
        response = self.app.delete(f'/api/listings/{lid}', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        # Verify status is soft-deleted in DB
        db_listing = models.get_listing_by_id(lid)
        self.assertIsNotNone(db_listing)
        self.assertEqual(db_listing['status'], 'REMOVED')

    # ==========================================
    # 2. SUPPORTING ENTITIES TESTS
    # ==========================================
    
    def test_07_reviews_crud(self):
        """Test Review Creation (Success, Self-Review Failure), Fetching, and Dynamic Seller Rating updating"""
        seller_id = VeriListWeek3TestCase.test_seller_id or 'seller_id_mock'
        if seller_id == 'seller_id_mock':
            # Resolve default seller account from DB to use
            seller = models.get_user_by_email('seller@gmail.com')
            if seller:
                seller_id = seller['id']
                
        # A: Self-review failure (Seller attempts to review self)
        headers_seller = self._get_headers(self.seller_token)
        payload_self = {
            'seller_id': seller_id,
            'rating': 5,
            'comment': 'I am the best seller!'
        }
        response = self.app.post('/api/reviews', data=json.dumps(payload_self), headers=headers_seller)
        self.assertEqual(response.status_code, 400)
        
        # B: Success review path (Buyer reviews Seller)
        headers_buyer = self._get_headers(self.buyer_token)
        payload_ok = {
            'seller_id': seller_id,
            'rating': 4,
            'comment': 'Fair price, smooth communication and transaction.',
            'listing_id': VeriListWeek3TestCase.test_listing_id
        }
        response = self.app.post('/api/reviews', data=json.dumps(payload_ok), headers=headers_buyer)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('review', data)
        self.assertEqual(data['review']['rating'], 4)
        
        # Verify dynamic seller profile ratings updated
        seller_profile = models.get_user_by_id(seller_id)
        self.assertIn('average_rating', seller_profile)
        self.assertGreaterEqual(seller_profile['total_reviews'], 1)
        
        # C: Read reviews list
        response = self.app.get(f'/api/reviews/seller/{seller_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('reviews', data)
        self.assertTrue(len(data['reviews']) > 0)

    def test_08_notifications_crud(self):
        """Test Notifications Retrieval and Mark as Read"""
        headers = self._get_headers(self.seller_token)
        
        # A: Fetch notifications
        response = self.app.get('/api/notifications', headers=headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('notifications', data)
        
        # Find one unread notification to test reading
        unread_notifs = [n for n in data['notifications'] if n['is_read'] == 0]
        if unread_notifs:
            notif_id = unread_notifs[0]['id']
            # Mark read
            response = self.app.post(f'/api/notifications/{notif_id}/read', headers=headers)
            self.assertEqual(response.status_code, 200)
            
            # Double check status in DB
            db_notifs = models.get_notifications_for_user(models.get_user_by_email('seller@gmail.com')['id'])
            for n in db_notifs:
                if n['id'] == notif_id:
                    self.assertEqual(n['is_read'], 1)

    def test_09_admin_endpoints(self):
        """Test Admin actions (Users audit, listings list) and checks authorization rules"""
        # A: Buyer tries admin endpoint -> should fail with 403
        headers_buyer = self._get_headers(self.buyer_token)
        response = self.app.get('/api/admin/users', headers=headers_buyer)
        self.assertEqual(response.status_code, 403)
        
        # B: Admin fetches all users -> success 200
        headers_admin = self._get_headers(self.admin_token)
        response = self.app.get('/api/admin/users', headers=headers_admin)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('users', data)
        self.assertTrue(len(data['users']) > 0)

        # C: Admin fetches all listings including flagged/removed -> success 200
        response = self.app.get('/api/admin/listings', headers=headers_admin)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('listings', data)
        self.assertTrue(len(data['listings']) > 0)

    # ==========================================
    # 3. CENTRALIZED ERROR & VALIDATION RESPONSE SHAPE
    # ==========================================
    
    def test_10_consistent_error_shape(self):
        """Check standard 404, 401 error response shapes are consistent"""
        # Route 404 (non-existent path)
        response = self.app.get('/api/some-random-route-that-does-not-exist')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['success'], False)
        self.assertIn('error', data)
        self.assertEqual(data['status_code'], 404)

        # Route 401 (auth required)
        response = self.app.get('/api/notifications', headers=self._get_headers(None)) # lacks auth token header
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['success'], False)
        self.assertIn('error', data)
        self.assertEqual(data['status_code'], 401)

    # ==========================================
    # 4. ADVANCED SSE NOTIFICATION STREAM
    # ==========================================

    def test_11_sse_notifications_stream(self):
        """Test Server-Sent Events real-time notification endpoint"""
        headers = self._get_headers(self.seller_token)
        # Establish connection with test client stream reading
        response = self.app.get('/api/notifications/stream', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/event-stream')
        
        # Read the first event from stream (CONNECTED status ping)
        iterator = response.iter_encoded()
        first_line = next(iterator).decode('utf-8')
        self.assertIn('CONNECTED', first_line)

if __name__ == '__main__':
    unittest.main()
