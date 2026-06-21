import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import credentials, firestore
cred = credentials.Certificate("serviceAccountKey.json")
app = firebase_admin.initialize_app(cred)
db = firestore.client(app, database_id="default")
print("Client created, trying write...")
db.collection("connection_test").document("ping").set({"status": "ok"})
print("SUCCESS - Firestore connection works!")
