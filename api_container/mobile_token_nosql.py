from typing import Optional, List, Dict
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure
import logging as logger
import os
import sys
import uuid
from firebase_admin import messaging
from lib.utils import get_actual_time, get_mongo_client

HOUR = 60 * 60
MINUTE = 60
MILLISECOND = 1_000

# TODO: (General) -> Create tests for each method && add the required checks in each method

class MobileToken:
    """
    MobileToken class that stores data in a MongoDB collection.
    Fields:
    - user_id: str (unique) [pk]
    - mobile_token: str: The mobile token of the user
    - created_at: int: The timestamp of the creation of the mobile token
    - updated_at: int: The timestamp of the last update of the mobile token
    """

    def __init__(self, test_client=None, test_db=None):
        self.client = test_client or get_mongo_client()
        if not self._check_connection():
            raise Exception("Failed to connect to MongoDB")
        if test_client:
            self.db = self.client[os.getenv('MONGO_TEST_DB')]
        else:
            self.db = self.client[test_db or os.getenv('MONGO_DB')]
        self.collection = self.db['chats']
        self.notifications = self.db['notifications']
        self._create_collection()
    
    def _check_connection(self):
        try:
            self.client.admin.command('ping')
        except Exception as e:
            logger.error(e)
            return False
        return True

    def _create_collection(self):
        try:
            self.collection.create_index([('user_id', ASCENDING)], unique=True)
            self.notifications.create_index([('user_id', ASCENDING)], unique=True)
        except DuplicateKeyError:
            logger.warning("Index on 'user_id' already exists.")
            
    def _get_user_notifications(self, user_id: str) -> Optional[Dict]:
        notifications = self.notifications.find_one({'user_id': user_id})
        return notifications or None
    
    def _add_user_to_notifications(self, user_id: str):
        actual_time = get_actual_time()
        try:
            self.notifications.insert_one({
                'user_id': user_id,
                'notifications': [],
                'created_at': actual_time,
                'updated_at': actual_time
            })
        except DuplicateKeyError:
            logger.warning(f"User {user_id} already exists in notifications.")
            
    def _save_notification(self, user_id: str, title: str, message: str):
        notifications = self._get_user_notifications(user_id)
        if not notifications:
            self._add_user_to_notifications(user_id)
            notifications = self._get_user_notifications(user_id)
        actual_time = get_actual_time()
        notifications['notifications'].append({
            'title': title,
            'message': message,
            'created_at': actual_time
        })
        self.notifications.update_one({'user_id': user_id}, {
            '$set': {
                'notifications': notifications['notifications'],
                'updated_at': actual_time
            }
        })
        
    def get_notifications(self, user_id: str, delete: bool = False) -> List[Dict]:
        notifications = self._get_user_notifications(user_id)
        if not notifications:
            return []
        if delete:
            self.notifications.update_one({'user_id': user_id}, {
                '$set': {
                    'notifications': [],
                    'updated_at': get_actual_time()
                }
            })
        return notifications['notifications']

    def update_mobile_token(self, user_id: str, mobile_token: str):
        actual_time = get_actual_time()
        if not self.collection.find_one({'user_id': user_id}):
            self.collection.insert_one({
                'user_id': user_id,
                'mobile_token': mobile_token,
                'created_at': actual_time,
                'updated_at': actual_time
            })
            return
        self.collection.update_one({'user_id': user_id}, {
            '$set': {
                'mobile_token': mobile_token,
                'updated_at': actual_time
            }
        })

    def get_mobile_token(self, user_id: str) -> Optional[str]:
        mobile_token = self.collection.find_one({'user_id': user_id}) or {}
        return mobile_token.get('mobile_token')
    
def send_notification(mobile_token_manager: MobileToken, user_id: str, title: str, message: str):
    mobile_token_manager._save_notification(user_id, title, message)
    
    ## Uncomment the following lines to send notifications using Firebase
    # token = mobile_token_manager.get_mobile_token(user_id)
    # if not token:
    #     logger.error(f"Failed to send notification to user {user_id}: No mobile token found")
    #     return
    # message = messaging.Message(
    #                 notification=messaging.Notification(
    #                     title=title,
    #                     body=message,
    #                 ),
    #                 token=token
    #             )
    # messaging.send(message)