
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

    def delete_user(self, uid):
        auth.delete_user(uid)
        print(f"Successfully deleted user: {uid}")

    def get_user(self, uid):
        user = auth.get_user(uid)
        print(f"Successfully retrieved user: {user.uid}")
        return user

    def send_email_verification(self, uid):
        try:
            auth.generate_email_verification_link(uid)
        except auth.UserNotFoundError:
            print(f"User not found: {uid}")
        except auth.FirebaseError:
            print(f"Error sending email verification to {uid}")

    def is_email_verified(self, uid):
        user = auth.get_user(uid)
        return user.email_verified

    def password_reset(self, email):
        try:
            auth.generate_password_reset_link(email)
        except auth.UserNotFoundError:
            print(f"User not found: {email}")
        except auth.FirebaseError:
            print(f"Error sending password reset link to {email}")
        except auth.ValueError:
            print(f"Invalid email: {email}")
