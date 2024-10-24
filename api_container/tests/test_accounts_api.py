import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os
import sys
from sqlalchemy import MetaData

# Run with the following command:
# pytest AccountsService/api_container/tests/test_accounts_api.py

# Set the TESTING environment variable
os.environ['TESTING'] = '1'

# Set a default DATABASE_URL for testing
os.environ['DATABASE_URL'] = 'sqlite:///test.db'

# Add the necessary paths to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))

from accounts_api import app, sql_manager, firebase_manager

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup code: runs before each test
    metadata = MetaData()
    metadata.reflect(bind=sql_manager.engine)
    metadata.drop_all(bind=sql_manager.engine)
    metadata.create_all(bind=sql_manager.engine)
    yield
    # Teardown code: runs after each test
    metadata.reflect(bind=sql_manager.engine)
    metadata.drop_all(bind=sql_manager.engine)
    metadata.create_all(bind=sql_manager.engine)

def test_get_account():
    # Mock the database response
    sql_manager.insert("testuser", "uid123", "Test User", "test@example.com", None, False, None, "2000-01-01")
    
    response = client.get("/testuser")
    assert response.status_code == 200
    
    response_json = response.json()
    assert response_json["username"] == "testuser"
    assert response_json["uuid"] == "uid123"
    assert response_json["complete_name"] == "Test User"
    assert response_json["email"] == "test@example.com"
    assert response_json["profile_picture"] is None
    assert response_json["is_provider"] is False
    assert response_json["description"] is None
    assert response_json["birth_date"] == "2000-01-01"

@pytest.mark.usefixtures("mocker")
def test_create_account(mocker):
    # Mock FirebaseManager.create_user
    mocker.patch.object(firebase_manager, 'create_user', return_value=type('obj', (object,), {'uid': 'uid123'}))
    
    body = {
        "username": "newuser",
        "password": "password123",
        "complete_name": "New User",
        "email": "new@example.com",
        "is_provider": False,
        "birth_date": "2000-01-01"
    }
    response = client.post("/create", json=body)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "user_id": "uid123"}

def test_delete_account():
    # Mock the database response
    sql_manager.insert("testuser", "uid123", "Test User", "test@example.com", None, False, None, "2000-01-01")
    
    response = client.delete("/testuser")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_update_account():
    # Mock the database response
    sql_manager.insert("testuser", "uid123", "Test User", "test@example.com", None, False, None, "2000-01-01")
    
    body = {
        "complete_name": "Updated User",
        "email": "updated@example.com"
    }
    response = client.put("/testuser", json=body)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    updated_account = sql_manager.get("testuser")
    assert updated_account["complete_name"] == "Updated User"
    assert updated_account["email"] == "updated@example.com"