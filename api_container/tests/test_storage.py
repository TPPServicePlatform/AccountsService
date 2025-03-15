import pytest
from unittest.mock import patch
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from lib.utils import save_file, get_file, delete_file

# Run with the following command:
# pytest AccountsService/api_container/tests/test_storage.py

# Set the TESTING environment variable
os.environ['TESTING'] = '1'
os.environ['MONGO_TEST_DB'] = 'test_db'

@pytest.fixture(autouse=True)
def mock_storage_path(tmpdir):
    os.environ['LOCAL_STORAGE_PATH'] = "AccountsService/api_container/tests/files/tmp"
    yield tmpdir
    for file in os.listdir(os.environ['LOCAL_STORAGE_PATH']):
        os.remove(os.path.join(os.environ['LOCAL_STORAGE_PATH'], file))
    os.rmdir(os.environ['LOCAL_STORAGE_PATH'])
    del os.environ['LOCAL_STORAGE_PATH']

def test_save_file():
    content = 'Hello, World!'
    
    path = save_file('test_provider', content)
    
    with open(path, 'r') as f:
        assert f.read() == content

def test_get_file():
    content = 'Hello, World!'
    
    path = save_file('test_provider', content)
    
    assert get_file(path).decode('utf-8') == content
    
def test_delete_file():
    content = 'Hello, World!'
    
    path = save_file('test_provider', content)
    
    delete_file(path)
    
    assert not os.path.exists(path)
