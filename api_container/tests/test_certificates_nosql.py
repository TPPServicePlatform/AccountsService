import pytest
import mongomock
from unittest.mock import patch
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from certificates_nosql import Certificates

# Run with the following command:
# pytest AccountsService/api_container/tests/test_certificates_nosql.py

# Set the TESTING environment variable
os.environ['TESTING'] = '1'
os.environ['MONGOMOCK'] = '1'

# Set a default MONGO_TEST_DB for testing
os.environ['MONGO_TEST_DB'] = 'test_db'

@pytest.fixture(scope='function')
def mongo_client():
    client = mongomock.MongoClient()
    yield client
    client.drop_database(os.getenv('MONGO_TEST_DB'))
    client.close()

@pytest.fixture(scope='function')
def certificates(mongo_client):
    return Certificates(test_client=mongo_client)

def test_insert_certificate(certificates, mocker):
    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-01 00:00:00")
    mocker.patch('certificates_nosql.uuid.uuid4', return_value='certificate_1')
    certificate_id = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 1',
        description='This is a test certificate.',
        path='/path/to/certificate_1'
    )
    assert certificate_id is not None
    assert certificate_id == 'certificate_1'

def test_get_provider_certificates(certificates, mocker):
    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-01 00:00:00")
    
    provider_certificates = certificates.get_provider_certificates('provider_1')
    assert provider_certificates is None

    certificate_id = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 1',
        description='This is a test certificate.',
        path='/path/to/certificate_1'
    )
    assert certificate_id is not None

    provider_certificates = certificates.get_provider_certificates('provider_1')
    assert provider_certificates is not None
    assert len(provider_certificates) == 1
    assert provider_certificates[0]['certificate_id'] == certificate_id

def test_get_certificate(certificates, mocker):
    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-01 00:00:00")
    
    certificate_id = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 1',
        description='This is a test certificate.',
        path='/path/to/certificate_1'
    )
    assert certificate_id is not None

    certificate = certificates.get_certificate_info('provider_1', certificate_id)
    assert certificate is not None
    assert certificate['certificate_id'] == certificate_id
    assert certificate['name'] == 'Certificate 1'
    assert certificate['description'] == 'This is a test certificate.'
    assert certificate['path'] == '/path/to/certificate_1'
    assert certificate['is_validated'] == False
    assert certificate['created_at'] == '2023-01-01 00:00:00'
    assert certificate['last_update_at'] == '2023-01-01 00:00:00'
    assert certificate['expiration_date'] is None

def test_update_certificate(certificates, mocker):
    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-01 00:00:00")
    
    certificate_id = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 1',
        description='This is a test certificate.',
        path='/path/to/certificate_1'
    )
    assert certificate_id is not None

    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-02 00:00:00")

    updated = certificates.update_certificate(
        provider_id='provider_1',
        certificate_id=certificate_id,
        name='Certificate 1',
        description='This is a test certificate.',
        path='/path/to/certificate_1',
        is_validated=True,
        expiration_date="2025-01-01 00:00:00"
    )
    assert updated is True

    certificate = certificates.get_certificate_info('provider_1', certificate_id)
    assert certificate is not None
    assert certificate['certificate_id'] == certificate_id
    assert certificate['name'] == 'Certificate 1'
    assert certificate['description'] == 'This is a test certificate.'
    assert certificate['path'] == '/path/to/certificate_1'
    assert certificate['is_validated'] == True
    assert certificate['created_at'] == '2023-01-01 00:00:00'
    assert certificate['last_update_at'] == '2023-01-02 00:00:00'
    assert certificate['expiration_date'] == "2025-01-01 00:00:00"

def test_delete_certificate(certificates, mocker):
    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-01 00:00:00")
    
    certificate_id = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 1',
        description='This is a test certificate.',
        path='/path/to/certificate_1'
    )
    assert certificate_id is not None

    deleted = certificates.delete_certificate('provider_1', certificate_id)
    assert deleted is True

    certificate = certificates.get_certificate_info('provider_1', certificate_id)
    assert certificate is None

def test_delete_provider_certificates(certificates, mocker):
    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-01 00:00:00")
    
    certificate_id = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 1',
        description='This is a test certificate.',
        path='/path/to/certificate_1'
    )
    assert certificate_id is not None

    deleted = certificates.delete_provider_certificates('provider_1')
    assert deleted is True

    provider_certificates = certificates.get_provider_certificates('provider_1')
    assert provider_certificates is None

def test_get_unverified_certificates(certificates, mocker):
    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-01 00:00:00")
    
    certificate_id_1 = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 1',
        description='This is a test certificate.',
        path='/path/to/certificate_1'
    )
    assert certificate_id_1 is not None

    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-02 00:00:00")

    certificate_id_2 = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 2',
        description='This is a test certificate.',
        path='/path/to/certificate_2'
    )
    assert certificate_id_2 is not None

    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-03 00:00:00")

    certificate_id_3 = certificates.add_certificate(
        provider_id='provider_1',
        name='Certificate 3',
        description='This is a test certificate.',
        path='/path/to/certificate_3'
    )
    assert certificate_id_3 is not None

    mocker.patch('certificates_nosql.get_actual_time', return_value="2023-01-04 00:00:00")

    certificates.update_certificate(
        provider_id='provider_1',
        certificate_id=certificate_id_2,
        name='Certificate 2',
        description='This is a test certificate.',
        path='/path/to/certificate_2',
        is_validated=True,
        expiration_date="2025-01-01 00:00:00"
    )

    unverified_certificates = certificates.get_unverified_certificates(limit=10, offset=0)
    assert unverified_certificates is not None
    assert len(unverified_certificates) == 2
    assert unverified_certificates[0]['certificate_id'] == certificate_id_1
    assert unverified_certificates[1]['certificate_id'] == certificate_id_3
