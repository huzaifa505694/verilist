import os
import firebase_admin
from firebase_admin import credentials, firestore

db = None

def get_firestore_db():
    """
    Initializes the Firebase Admin SDK and returns the Firestore client.
    """
    global db
    if db is not None:
        return db
        
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'backend/service-account.json')
    
    # Resolve relative path based on workspace root if needed
    if not os.path.isabs(cred_path):
        # Resolve path relative to the project root (Verilist root)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        abs_path = os.path.join(project_root, cred_path)
    else:
        abs_path = cred_path
        
    if os.path.exists(abs_path):
        cred = credentials.Certificate(abs_path)
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(cred)
    else:
        raise FileNotFoundError(
            f"Firebase service account credentials file not found at: {abs_path}\n"
            "Please go to the Firebase Console -> Project Settings -> Service Accounts, "
            "generate a new private key (JSON), rename it to 'service-account.json', "
            "and place it in your 'backend/' folder."
        )
        
    db = firestore.client()
    return db
