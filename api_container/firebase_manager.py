
import firebase_admin
from firebase_admin import credentials, auth


class FirebaseManager():

    def __init__(self):
        self.firebase_app = firebase_admin.initialize_app(
            credentials.Certificate("credentials_firebase.json"))

    def create_user(self, email, password):
        created_user = auth.create_user(email=email, password=password)
        print(f"Successfully created user: {created_user.uid}")
        return created_user
