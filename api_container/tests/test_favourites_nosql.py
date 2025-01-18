import pytest
import mongomock
from unittest.mock import patch
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from favourites_nosql import Favourites

# Run with the following command:
# pytest AccountsService/api_container/tests/test_favourites_nosql.py

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
def favourites(mongo_client):
    return Favourites(test_client=mongo_client)

def test_add_favourite_provider(favourites, mocker):
    result = favourites.add_favourite_provider(client_id='client_1', provider_id='provider_1')
    assert result is True

def test_remove_favourite_provider(favourites, mocker):
    favourites.add_favourite_provider(client_id='client_1', provider_id='provider_1')
    result = favourites.remove_favourite_provider(client_id='client_1', provider_id='provider_1')
    assert result is True

def test_get_favourite_providers(favourites, mocker):
    favourites.add_favourite_provider(client_id='client_1', provider_id='provider_1')
    providers = favourites.get_favourite_providers(client_id='client_1')
    assert len(providers) == 1
    assert 'provider_1' in providers

def test_multiple_favourite_providers(favourites, mocker):
    favourites.add_favourite_provider(client_id='client_1', provider_id='provider_1')
    providers = favourites.get_favourite_providers(client_id='client_1')
    assert len(providers) == 1
    assert 'provider_1' in providers

    favourites.add_favourite_provider(client_id='client_1', provider_id='provider_2')
    providers = favourites.get_favourite_providers(client_id='client_1')
    assert len(providers) == 2
    assert all(provider in providers for provider in ['provider_1', 'provider_2'])

    favourites.remove_favourite_provider(client_id='client_1', provider_id='provider_1')
    providers = favourites.get_favourite_providers(client_id='client_1')
    assert len(providers) == 1
    assert 'provider_1' not in providers
    assert 'provider_2' in providers

def test_multiple_clients_favourite_providers(favourites, mocker):
    favourites.add_favourite_provider(client_id='client_1', provider_id='provider_1')
    favourites.add_favourite_provider(client_id='client_2', provider_id='provider_1')
    favourites.add_favourite_provider(client_id='client_2', provider_id='provider_2')
    providers = favourites.get_favourite_providers(client_id='client_1')
    assert len(providers) == 1
    assert 'provider_1' in providers
    assert 'provider_2' not in providers
    providers = favourites.get_favourite_providers(client_id='client_2')
    assert len(providers) == 2
    assert all(provider in providers for provider in ['provider_1', 'provider_2'])

    favourites.remove_favourite_provider(client_id='client_1', provider_id='provider_1')
    providers = favourites.get_favourite_providers(client_id='client_1')
    assert len(providers) == 0
    providers = favourites.get_favourite_providers(client_id='client_2')
    assert len(providers) == 2
    assert all(provider in providers for provider in ['provider_1', 'provider_2'])

def test_add_folder(favourites, mocker):
    result = favourites.add_folder(client_id='client_1', folder_name='folder_1')
    assert result is True

def test_remove_folder(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    result = favourites.remove_folder(client_id='client_1', folder_name='folder_1')
    assert result is True

def test_get_saved_folders(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    folders = favourites.get_saved_folders(client_id='client_1')
    assert len(folders) == 1
    assert 'folder_1' in folders

def test_multiple_saved_folders(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    folders = favourites.get_saved_folders(client_id='client_1')
    assert len(folders) == 1
    assert 'folder_1' in folders

    favourites.add_folder(client_id='client_1', folder_name='folder_2')
    folders = favourites.get_saved_folders(client_id='client_1')
    assert len(folders) == 2
    assert all(folder in folders for folder in ['folder_1', 'folder_2'])

    favourites.remove_folder(client_id='client_1', folder_name='folder_1')
    folders = favourites.get_saved_folders(client_id='client_1')
    assert len(folders) == 1
    assert 'folder_1' not in folders
    assert 'folder_2' in folders

def test_multiple_clients_saved_folders(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    favourites.add_folder(client_id='client_2', folder_name='folder_1')
    favourites.add_folder(client_id='client_2', folder_name='folder_2')
    folders = favourites.get_saved_folders(client_id='client_1')
    assert len(folders) == 1
    assert 'folder_1' in folders
    assert 'folder_2' not in folders
    folders = favourites.get_saved_folders(client_id='client_2')
    assert len(folders) == 2
    assert all(folder in folders for folder in ['folder_1', 'folder_2'])

    favourites.remove_folder(client_id='client_1', folder_name='folder_1')
    folders = favourites.get_saved_folders(client_id='client_1')
    assert len(folders) == 0
    folders = favourites.get_saved_folders(client_id='client_2')
    assert len(folders) == 2
    assert all(folder in folders for folder in ['folder_1', 'folder_2'])

def test_add_service_to_folder(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    result = favourites.add_service_to_folder(client_id='client_1', folder_name='folder_1', service_id='service_1')
    assert result is True

def test_remove_service_from_folder(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    favourites.add_service_to_folder(client_id='client_1', folder_name='folder_1', service_id='service_1')
    result = favourites.remove_service_from_folder(client_id='client_1', folder_name='folder_1', service_id='service_1')
    assert result is True

def test_get_folder_services(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    favourites.add_service_to_folder(client_id='client_1', folder_name='folder_1', service_id='service_1')
    services = favourites.get_folder_services(client_id='client_1', folder_name='folder_1')
    assert len(services) == 1
    assert 'service_1' in services

def test_multiple_folder_services(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    favourites.add_service_to_folder(client_id='client_1', folder_name='folder_1', service_id='service_1')
    services = favourites.get_folder_services(client_id='client_1', folder_name='folder_1')
    assert len(services) == 1
    assert 'service_1' in services

    favourites.add_service_to_folder(client_id='client_1', folder_name='folder_1', service_id='service_2')
    services = favourites.get_folder_services(client_id='client_1', folder_name='folder_1')
    assert len(services) == 2
    assert all(service in services for service in ['service_1', 'service_2'])

    favourites.remove_service_from_folder(client_id='client_1', folder_name='folder_1', service_id='service_1')
    services = favourites.get_folder_services(client_id='client_1', folder_name='folder_1')
    assert len(services) == 1
    assert 'service_1' not in services
    assert 'service_2' in services

def test_multiple_folders_services(favourites, mocker):
    favourites.add_folder(client_id='client_1', folder_name='folder_1')
    favourites.add_service_to_folder(client_id='client_1', folder_name='folder_1', service_id='service_1')
    favourites.add_service_to_folder(client_id='client_1', folder_name='folder_1', service_id='service_2')
    favourites.add_folder(client_id='client_1', folder_name='folder_2')
    favourites.add_service_to_folder(client_id='client_1', folder_name='folder_2', service_id='service_3')
    favourites.add_service_to_folder(client_id='client_1', folder_name='folder_2', service_id='service_4')
    services = favourites.get_folder_services(client_id='client_1', folder_name='folder_1')
    assert len(services) == 2
    assert all(service in services for service in ['service_1', 'service_2'])
    services = favourites.get_folder_services(client_id='client_1', folder_name='folder_2')
    assert len(services) == 2
    assert all(service in services for service in ['service_3', 'service_4'])

    favourites.remove_service_from_folder(client_id='client_1', folder_name='folder_1', service_id='service_1')
    services = favourites.get_folder_services(client_id='client_1', folder_name='folder_1')
    assert len(services) == 1
    assert 'service_1' not in services
    assert 'service_2' in services

    favourites.remove_service_from_folder(client_id='client_1', folder_name='folder_2', service_id='service_3')
    services = favourites.get_folder_services(client_id='client_1', folder_name='folder_2')
    assert len(services) == 1
    assert 'service_3' not in services
    assert 'service_4' in services
