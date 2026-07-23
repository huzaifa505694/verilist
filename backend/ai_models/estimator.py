import os
import joblib
import pandas as pd
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'price_estimator.pkl')

class PriceEstimator:
    _model_data = None

    @classmethod
    def get_model_data(cls):
        if cls._model_data is None:
            if os.path.exists(MODEL_PATH):
                try:
                    loaded = joblib.load(MODEL_PATH)
                    if isinstance(loaded, dict):
                        cls._model_data = loaded
                    else:
                        # Fallback for old pipeline-only files
                        cls._model_data = {
                            'pipeline': loaded,
                            'residual_std': 2500.0,
                            'feature_importances': {
                                'year': 0.35,
                                'odometer': 0.30,
                                'condition': 0.20,
                                'model': 0.10,
                                'make': 0.05
                            }
                        }
                    print("Loaded AI Price Estimator model data successfully.")
                except Exception as e:
                    print(f"Error loading price estimator model: {e}")
            else:
                print("Price estimator model file not found. Running with fallback heuristic model.")
        return cls._model_data

    @classmethod
    def estimate_price(cls, year: int, make: str, model: str, mileage: int, condition_label: str) -> tuple:
        """
        Estimates the fair market price range of a vehicle.
        condition_label can be: 'EXCELLENT', 'GOOD', 'FAIR', 'POOR'
        
        Returns:
            (predicted_price, min_price, max_price)
        """
        if year is None or make is None or model is None or mileage is None or condition_label is None:
            return None, None, None
            
        # Map condition label to numeric value (1.0 to 5.0 in the dataset)
        condition_map = {
            'EXCELLENT': 4.5,
            'GOOD': 3.5,
            'FAIR': 2.5,
            'POOR': 1.5
        }
        condition_numeric = condition_map.get(str(condition_label).upper(), 3.4)
        
        model_data = cls.get_model_data()
        
        if model_data is not None:
            try:
                model_pipeline = model_data.get('pipeline')
                residual_std = model_data.get('residual_std', 2500.0)
                
                # Create a single row DataFrame
                X = pd.DataFrame([{
                    'year': int(year),
                    'make': str(make),
                    'model': str(model),
                    'odometer': float(mileage),
                    'condition': float(condition_numeric)
                }])
                
                predicted = float(model_pipeline.predict(X)[0])
                # Clamp to a minimum of $500
                predicted = max(500.0, round(predicted, -2))
                
                # Generate a confidence range based on z-score of residual std deviation
                min_price = max(500.0, round(predicted - 1.96 * residual_std, -2))
                max_price = max(500.0, round(predicted + 1.96 * residual_std, -2))
                
                return predicted, min_price, max_price
            except Exception as e:
                print(f"AI prediction failed: {e}. Using fallback heuristic.")
                
        # Fallback Heuristic (Depreciation Model)
        # Base original value of cars
        premium_makes = ['Tesla', 'BMW', 'Audi', 'Mercedes', 'Mercedes-Benz', 'Lexus', 'Land Rover']
        base_val = 55000.0 if make in premium_makes else 35000.0
        
        years_old = 2026 - int(year)
        # 8% depreciation per year
        depreciated = base_val - (years_old * (base_val * 0.08))
        # $0.12 depreciation per mile
        depreciated -= (float(mileage) * 0.12)
        
        # Condition scaling
        condition_factors = {
            'EXCELLENT': 1.1,
            'GOOD': 0.95,
            'FAIR': 0.75,
            'POOR': 0.5
        }
        factor = condition_factors.get(condition_label.upper(), 0.9)
        predicted = depreciated * factor
        
        # Clamp to minimum $1,000
        predicted = max(1000.0, round(predicted, -2))
        
        min_price = max(800.0, round(predicted * 0.85, -2))
        max_price = round(predicted * 1.15, -2)
        
        return predicted, min_price, max_price

    @classmethod
    def get_feature_importances(cls):
        model_data = cls.get_model_data()
        if model_data is not None and isinstance(model_data, dict):
            return model_data.get('feature_importances', {})
        return {
            'year': 0.35,
            'odometer': 0.30,
            'condition': 0.20,
            'model': 0.10,
            'make': 0.05
        }

ELECTRONICS_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'electronics_estimator.pkl')

class ElectronicsEstimator:
    _model_data = None

    @classmethod
    def get_model_data(cls):
        if cls._model_data is None:
            if os.path.exists(ELECTRONICS_MODEL_PATH):
                try:
                    loaded = joblib.load(ELECTRONICS_MODEL_PATH)
                    if isinstance(loaded, dict):
                        cls._model_data = loaded
                    print("Loaded AI Electronics Price Estimator model data successfully.")
                except Exception as e:
                    print(f"Error loading electronics price estimator: {e}")
        return cls._model_data

    @classmethod
    def estimate_price(cls, brand: str, category_name: str, condition_label: str) -> tuple:
        """
        Estimates the fair market price range of an electronics item.
        condition_label can be: 'EXCELLENT', 'GOOD', 'FAIR', 'POOR'
        
        Returns:
            (predicted_price, min_price, max_price)
        """
        if brand is None or category_name is None or condition_label is None:
            return None, None, None

        condition_map = {
            'EXCELLENT': 1.0,
            'GOOD': 2.0,
            'FAIR': 3.0,
            'POOR': 4.0
        }
        condition_numeric = condition_map.get(str(condition_label).upper(), 2.0)
        
        model_data = cls.get_model_data()
        
        if model_data is not None:
            try:
                model_pipeline = model_data.get('pipeline')
                residual_std = model_data.get('residual_std', 25.0)
                
                # Features: ['brand_name', 'category_name', 'item_condition_id', 'shipping']
                # category_name should match the sub-category or default path
                cat_path = category_name
                if '/' not in cat_path:
                    # Default sub-category mapping for simple model inputs
                    cat_path = f"Electronics/Cell Phones & Accessories/{category_name}"
                
                X = pd.DataFrame([{
                    'brand_name': str(brand),
                    'category_name': str(cat_path),
                    'item_condition_id': float(condition_numeric),
                    'shipping': 0.0  # Default shipping
                }])
                
                predicted = float(model_pipeline.predict(X)[0])
                predicted = max(5.0, round(predicted, 1))
                
                # Generate range based on z-score of residual std deviation
                min_price = max(5.0, round(predicted - 1.96 * residual_std, 1))
                max_price = max(5.0, round(predicted + 1.96 * residual_std, 1))
                
                return predicted, min_price, max_price
            except Exception as e:
                print(f"AI electronics prediction failed: {e}. Using fallback heuristic.")
                
        # Fallback Heuristic
        premium_brands = ['Apple', 'Samsung', 'Sony', 'Nintendo']
        base_val = 500.0 if brand in premium_brands else 150.0
        
        condition_factors = {
            'EXCELLENT': 1.0,
            'GOOD': 0.8,
            'FAIR': 0.5,
            'POOR': 0.2
        }
        factor = condition_factors.get(condition_label.upper(), 0.7)
        predicted = base_val * factor
        
        predicted = max(10.0, round(predicted, 1))
        min_price = max(5.0, round(predicted * 0.8, 1))
        max_price = round(predicted * 1.2, 1)
        
        return predicted, min_price, max_price

    @classmethod
    def get_feature_importances(cls):
        model_data = cls.get_model_data()
        if model_data is not None and isinstance(model_data, dict):
            return model_data.get('feature_importances', {})
        return {
            'brand_name': 0.40,
            'category_name': 0.35,
            'item_condition_id': 0.20,
            'shipping': 0.05
        }

