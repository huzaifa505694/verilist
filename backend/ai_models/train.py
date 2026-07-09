import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

def train_model():
    dataset_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'car_prices.csv')
    model_dir = os.path.dirname(__file__)
    model_path = os.path.join(model_dir, 'price_estimator.pkl')
    
    print(f"Loading dataset from: {dataset_path}...")
    if not os.path.exists(dataset_path):
        print(f"Error: dataset not found at {dataset_path}")
        return
        
    # Read the dataset (we will drop rows with missing targets and skip bad lines)
    df = pd.read_csv(dataset_path, on_bad_lines='skip')
    print(f"Original shape: {df.shape}")
    
    # Drop rows with null sellingprice
    df = df.dropna(subset=['sellingprice'])
    
    # Fill missing values in categorical fields to avoid issues
    df['make'] = df['make'].fillna('Unknown').astype(str)
    df['model'] = df['model'].fillna('Unknown').astype(str)
    
    # Select features and target
    features = ['year', 'make', 'model', 'odometer', 'condition']
    target = 'sellingprice'
    
    X = df[features]
    y = df[target]
    
    print(f"Cleaned dataset shape: {X.shape}")
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)
    print(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples.")
    
    # Preprocessing pipelines
    num_features = ['year', 'odometer', 'condition']
    num_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])
    
    cat_features = ['make', 'model']
    cat_transformer = Pipeline(steps=[
        ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', num_transformer, num_features),
            ('cat', cat_transformer, cat_features)
        ]
    )
    
    # Combine preprocessor with Ridge regression model
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', Ridge(alpha=1.0))
    ])
    
    print("Training Ridge regression model...")
    model_pipeline.fit(X_train, y_train)
    print("Training completed.")
    
    # Evaluate model
    y_pred = model_pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"Evaluation Metrics on Test Set:")
    print(f" - Mean Absolute Error (MAE): ${mae:.2f}")
    print(f" - R^2 Score: {r2:.4f}")
    
    # Save the pipeline
    print(f"Saving trained model pipeline to {model_path}...")
    joblib.dump(model_pipeline, model_path)
    print("Model saved successfully.")

if __name__ == "__main__":
    train_model()
