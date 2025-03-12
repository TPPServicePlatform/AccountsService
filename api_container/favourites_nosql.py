from typing import Optional, List, Dict, Tuple
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure
import logging as logger
import os
import sys
import uuid
from lib.utils import get_actual_time, get_mongo_client

HOUR = 60 * 60
MINUTE = 60
MILLISECOND = 1_000

# TODO: (General) -> Create tests for each method && add the required checks in each method

class Favourites:
    """
    Favourites class that stores data in a MongoDB collection.
    Fields:
    - id: int (unique) [pk]
    - client_id (str): The id of the client account
    - favourite_providers (Set[str]): The list of favourite providers
    - saved_folders (Dict[str, Set[str]]): The list of saved services in each folder
    """

    def __init__(self, test_client=None, test_db=None):
        self.client = test_client or get_mongo_client()
        if not self._check_connection():
            raise Exception("Failed to connect to MongoDB")
        if test_client:
            self.db = self.client[os.getenv('MONGO_TEST_DB')]
        else:
            self.db = self.client[test_db or os.getenv('MONGO_DB')]
        self.collection = self.db['favourites']
        self._create_collection()
    
    def _check_connection(self):
        try:
            self.client.admin.command('ping')
        except Exception as e:
            logger.error(e)
            return False
        return True

    def _create_collection(self):
        self.collection.create_index([('uuid', ASCENDING)], unique=True)
    
    def _is_favourite_provider(self, client_id: str, provider_id: str) -> bool:
        return self.collection.find_one({'client_id': client_id, 'favourite_providers': {'$in': [provider_id]}}) is not None
    
    def _create_basic_document(self, client_id: str) -> bool:
        try:
            self.collection.insert_one({
                'uuid': str(uuid.uuid4()),
                'client_id': client_id,
                'favourite_providers': [], 'saved_folders': {}
                })
            return True
        except Exception as e:
            logger.error(e)
            return False
    
    def _client_has_document(self, client_id: str) -> bool:
        return self.collection.find_one({'client_id': client_id}) is not None
    
    def add_favourite_provider(self, client_id: str, provider_id: str) -> bool:
        if self._is_favourite_provider(client_id, provider_id):
            return True
        if not self._client_has_document(client_id):
            if not self._create_basic_document(client_id):
                return False
        try:
            self.collection.update_one({'client_id': client_id}, {'$addToSet': {'favourite_providers': provider_id}})
            return True
        except Exception as e:
            logger.error(e)
            return False
        
    def remove_favourite_provider(self, client_id: str, provider_id: str) -> bool:
        if not self._is_favourite_provider(client_id, provider_id):
            return True
        if not self._client_has_document(client_id):
            return False
        try:
            self.collection.update_one({'client_id': client_id}, {'$pull': {'favourite_providers': provider_id}})
            return True
        except Exception as e:
            logger.error(e)
            return False
    
    def get_favourite_providers(self, client_id: str) -> Optional[List[str]]:
        data = self.collection.find_one({'client_id': client_id})
        if not data:
            return None
        return data.get('favourite_providers', [])
        
    def folder_exists(self, client_id: str, folder_name: str) -> bool:
        return self.collection.find_one({'client_id': client_id, f'saved_folders.{folder_name}': {'$exists': True}}) is not None
    
    def add_folder(self, client_id: str, folder_name: str) -> bool:
        if self.folder_exists(client_id, folder_name):
            return True
        if not self._client_has_document(client_id):
            if not self._create_basic_document(client_id):
                return False
        try:
            self.collection.update_one({'client_id': client_id}, {'$set': {f'saved_folders.{folder_name}': []}})
            return True
        except Exception as e:
            logger.error(e)
            return False
        
    def remove_folder(self, client_id: str, folder_name: str) -> bool:
        if not self.folder_exists(client_id, folder_name):
            return True
        if not self._client_has_document(client_id):
            return False
        try:
            self.collection.update_one({'client_id': client_id}, {'$unset': {f'saved_folders.{folder_name}': ''}})
            return True
        except Exception as e:
            logger.error(e)
            return False
        
    def get_saved_folders(self, client_id: str) -> Optional[List[str]]:
        data = self.collection.find_one({'client_id': client_id})
        if not data:
            return None
        return list(data.get('saved_folders', {}).keys())

    def add_service_to_folder(self, client_id: str, folder_name: str, service_id: str) -> bool:
        if not self.folder_exists(client_id, folder_name):
            return False
        if not self._client_has_document(client_id):
            if not self._create_basic_document(client_id):
                return False
        try:
            self.collection.update_one({'client_id': client_id}, {'$addToSet': {f'saved_folders.{folder_name}': service_id}})
            return True
        except Exception as e:
            logger.error(e)
            return False

    def remove_service_from_folder(self, client_id: str, folder_name: str, service_id: str) -> bool:
        if not self.folder_exists(client_id, folder_name):
            return False
        if not self._client_has_document(client_id):
            return False
        try:
            self.collection.update_one({'client_id': client_id}, {'$pull': {f'saved_folders.{folder_name}': service_id}})
            return True
        except Exception as e:
            logger.error(e)
            return False
        
    def get_folder_services(self, client_id: str, folder_name: str) -> Optional[List[str]]:
        data = self.collection.find_one({'client_id': client_id})
        if not data:
            return None
        return data.get('saved_folders', {}).get(folder_name, [])
    
    def get_relations(self, available_services: List[str]) -> Optional[Dict[str, List[str]]]:
        try:
            pipeline = [
                {'$project': {
                    'client_id': 1,
                    'saved_folders': {'$objectToArray': '$saved_folders'}
                }},
                {'$unwind': '$saved_folders'},
                {'$match': {
                    'saved_folders.v': {'$in': available_services}
                }},
                {'$project': {
                    'client_id': 1,
                    'folder_name': '$saved_folders.k',
                    'services': {
                        '$filter': {
                            'input': '$saved_folders.v',
                            'as': 'service',
                            'cond': {'$in': ['$$service', available_services]}
                        }
                    }
                }}
            ]
            data = list(self.collection.aggregate(pipeline))
            relations = {}
            for record in data:
                complete_name = f"{record['client_id']}_{record['folder_name']}"
                relations[complete_name] = record['services']
            return relations
        except Exception as e:
            logger.error(e)
            return None
