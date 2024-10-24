
import firebase_admin
from firebase_admin import credentials, auth


class FirebaseManager():

    def __init__(self):
        try:
            self.firebase_app = firebase_admin.initialize_app(
                credentials.Certificate("credentials_firebase.json"))
            self.firebase_app = firebase_admin.get_app()
        except ValueError:
            print("Firebase app not initialized with credentials")

    def create_user(self, email, password):
        created_user = auth.create_user(email=email, password=password)
        print(f"Successfully created user: {created_user.uid}")
        return created_user

    def password_reset(self, email):
        try:
            auth.generate_password_reset_link(email)
        except auth.UserNotFoundError:
            print(f"User not found: {email}")
        except auth.FirebaseError:
            print(f"Error sending password reset link to {email}")
        except auth.ValueError:
            print(f"Invalid email: {email}")
