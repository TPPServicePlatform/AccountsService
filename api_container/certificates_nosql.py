from typing import Optional, List, Dict
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure
import logging as logger
import os
import sys
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from lib.utils import get_actual_time, get_mongo_client

HOUR = 60 * 60
MINUTE = 60
MILLISECOND = 1_000

# TODO: (General) -> Create tests for each method && add the required checks in each method

class Certificates:
    """
    Certificates class that stores data in a MongoDB collection.
    Fields:
    - uuid: int (unique) [pk] id of the provider account that the certificates belongs to
    - certificates (List[Dict]): The list of certificates
    - created_at (int): The timestamp of the creation of the certificates
    - last_update_at (int): The timestamp of the last update of the certificates

    Certificates structure:
    - certificate_id (str): The id of the certificate
    - name (str): The name of the certificate
    - description (str): The description of the certificate
    - path (str): The path of the certificate
    - created_at (int): The timestamp of the creation of the certificate
    - last_update_at (int): The timestamp of the last update of the certificate
    - is_validated (bool): The validity of the certificate
    - expiration_date (int): The timestamp of the expiration date of the certificate
    """

    def __init__(self, test_client=None, test_db=None):
        self.client = test_client or get_mongo_client()
        if not self._check_connection():
            raise Exception("Failed to connect to MongoDB")
        if test_client:
            self.db = self.client[os.getenv('MONGO_TEST_DB')]
        else:
            self.db = self.client[test_db or os.getenv('MONGO_DB')]
        self.collection = self.db['certificates']
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

    def _create_profile(self, provider_id: int):
        self.collection.insert_one({
            'uuid': provider_id,
            'certificates': [],
            'created_at': get_actual_time(),
            'last_update_at': get_actual_time()
        })

    def get_provider_certificates(self, provider_id: int) -> Optional[Dict]:
        pipeline = [
            {'$match': {'uuid': provider_id}},
            {'$unwind': '$certificates'},
            {'$project': {
                '_id': 0,
                'certificate_id': '$certificates.certificate_id',
                'name': '$certificates.name'
                }
            }
        ]
        return list(self.collection.aggregate(pipeline)) or None
    
    def get_certificate_info(self, provider_id: int, certificate_id: str) -> Optional[Dict]:
        pipeline = [
            {'$match': {'uuid': provider_id, 'certificates.certificate_id': certificate_id}},
            {'$unwind': '$certificates'},
            {'$project': {
                '_id': 0,
                'certificate_id': '$certificates.certificate_id',
                'name': '$certificates.name',
                'description': '$certificates.description',
                'path': '$certificates.path',
                'created_at': '$certificates.created_at',
                'last_update_at': '$certificates.last_update_at',
                'is_validated': '$certificates.is_validated',
                'expiration_date': '$certificates.expiration_date'
                }
            }
        ]
        result = list(self.collection.aggregate(pipeline))
        return result[0] if result else None
    
    def add_certificate(self, provider_id: int, name: str, description: str, path: str):
        if not self.collection.find_one({'uuid': provider_id}):
            self._create_profile(provider_id)
        certificate_id = str(uuid.uuid4())
        certificate = {
            'certificate_id': certificate_id,
            'name': name,
            'description': description,
            'path': path,
            'created_at': get_actual_time(),
            'last_update_at': get_actual_time(),
            'is_validated': False,
            'expiration_date': None
        }
        self.collection.update_one({'uuid': provider_id}, {'$push': {'certificates': certificate}})
        return certificate_id
    
    def update_certificate(self, provider_id: int, certificate_id: str, name: str, description: str, path: str, is_validated: bool, expiration_date: int) -> bool:
        if not self.get_certificate_info(provider_id, certificate_id):
            return False
        self.collection.update_one({'uuid': provider_id, 'certificates.certificate_id': certificate_id}, {
            '$set': {
                'certificates.$.name': name,
                'certificates.$.description': description,
                'certificates.$.path': path,
                'certificates.$.last_update_at': get_actual_time(),
                'certificates.$.is_validated': is_validated,
                'certificates.$.expiration_date': expiration_date,
                'last_update_at': get_actual_time()
            }
        })
        return True
    
    def delete_certificate(self, provider_id: int, certificate_id: str) -> bool:
        if not self.get_certificate_info(provider_id, certificate_id):
            return False
        result = self.collection.update_one({'uuid': provider_id}, {'$pull': {'certificates': {'certificate_id': certificate_id}}})
        return result.modified_count > 0
    
    def delete_provider_certificates(self, provider_id: int) -> bool:
        if not self.collection.find_one({'uuid': provider_id}):
            return False
        result = self.collection.delete_one({'uuid': provider_id})
        return result.deleted_count > 0
    
    def get_unverified_certificates(self, limit: int, offset: int) -> Optional[List[Dict]]:
        pipeline = [
            {'$unwind': '$certificates'},
            {'$match': {'certificates.is_validated': False}},
            {'$sort': {'certificates.created_at': ASCENDING}},
            {'$skip': offset},
            {'$limit': limit},
            {'$project': {
                '_id': 0,
                'uuid': 1,
                'certificate_id': '$certificates.certificate_id',
                'name': '$certificates.name',
                'description': '$certificates.description',
                'path': '$certificates.path',
                'created_at': '$certificates.created_at',
                'last_update_at': '$certificates.last_update_at',
                'expiration_date': '$certificates.expiration_date'
                }
            }
        ]
        return list(self.collection.aggregate(pipeline))
