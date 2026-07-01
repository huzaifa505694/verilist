import os
import joblib
import pandas as pd
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'price_estimator.pkl')

class PriceEstimator:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            if os.path.exists(MODEL_PATH):
                try:
                    cls._model = joblib.load(MODEL_PATH)
                    print("Loaded AI Price Estimator model successfully.")
                except Exception as e:
                    print(f"Error loading price estimator model: {e}")
            else:
                print("Price estimator model file not found. Running with fallback heuristic model.")
        return cls._model

    @classmethod
    def estimate_price(cls, year: int, make: str, model: str, mileage: int, condition_label: str) -> tuple:
        """
        Estimates the fair market price range of a vehicle.
        condition_label can be: 'EXCELLENT', 'GOOD', 'FAIR', 'POOR'
        
        Returns:
            (predicted_price, min_price, max_price)
        """
        # Map condition label to numeric value (1.0 to 5.0 in the dataset)
        condition_map = {
            'EXCELLENT': 4.5,
            'GOOD': 3.5,
            'FAIR': 2.5,
            'POOR': 1.5
        }
        condition_numeric = condition_map.get(condition_label.upper(), 3.4)
        
        model_pipeline = cls.get_model()
        
        if model_pipeline is not None:
            try:
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
                
                # Determine range (e.g. +/- 15%)
                min_price = max(500.0, round(predicted * 0.85, -2))
                max_price = round(predicted * 1.15, -2)
                
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
