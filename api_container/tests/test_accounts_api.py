from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
import os
import sys
from sqlalchemy import MetaData

# Run with the following command:
# pytest AccountsService/api_container/tests/test_accounts_api.py

# Set the TESTING environment variable
os.environ['TESTING'] = '1'
os.environ['MONGOMOCK'] = '1'

# Set a default DATABASE_URL for testing
os.environ['DATABASE_URL'] = 'sqlite:///test.db'

# Set a default MONGO_TEST_DB for testing
os.environ['MONGO_TEST_DB'] = 'test_db'

# Add the necessary paths to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))

from accounts_api import app, accounts_manager, firebase_manager, chats_manager, favourites_manager

# client = TestClient(app)

@pytest.fixture(scope='function')
def test_app():
    client = TestClient(app)
    yield client

@pytest.fixture(scope='function', autouse=True)
def setup_teardown():
    # Setup code: runs before each test
    metadata = MetaData()
    metadata.reflect(bind=accounts_manager.engine)
    metadata.drop_all(bind=accounts_manager.engine)
    accounts_manager.create_table()
    chats_manager.collection.drop()
    favourites_manager.collection.drop()
    yield
    # Teardown code: runs after each test
    metadata.reflect(bind=accounts_manager.engine)
    metadata.drop_all(bind=accounts_manager.engine)
    accounts_manager.create_table()
    chats_manager.collection.drop()
    favourites_manager.collection.drop()

def test_get_account(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("testuser", "uid123", "Test User", "test@example.com", None, False, None, "2000-01-01")
    
    response = test_app.get("/get/testuser")
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
def test_create_account(test_app, mocker):
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
    response = test_app.post("/create", json=body)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "user_id": "uid123"}

def test_delete_account(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("testuser", "uid123", "Test User", "test@example.com", None, False, None, "2000-01-01")
    
    response = test_app.delete("/delete/testuser")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_update_account(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("testuser", "uid123", "Test User", "test@example.com", None, False, None, "2000-01-01")
    
    body = {
        "complete_name": "Updated User",
        "email": "updated@example.com"
    }
    response = test_app.put("/update/testuser", json=body)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    updated_account = accounts_manager.get_by_username("testuser")
    assert updated_account["complete_name"] == "Updated User"
    assert updated_account["email"] == "updated@example.com"

def test_send_message(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("testuser", "uid123", "Test User", "test@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("testuser2", "uid456", "Test User 2", "test2@example.com", None, True, None, "2000-01-01")

    body = {
        "provider_id": "uid123",
        "client_id": "uid456",
        "message_content": "Hello, this is a test message."
    }
    response = test_app.put("/chats/uid123", json=body)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["status"] == "ok"
    assert response_json["chat_id"] is not None

    messages = chats_manager.get_messages("uid123", "uid456", 10, 0)
    assert len(messages) == 1

def test_get_chat(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("testuser", "uid123", "Test User", "test@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("testuser2", "uid456", "Test User 2", "test2@example.com", None, True, None, "2000-01-01")

    for i in range(5):
        body = {
            "provider_id": "uid123",
            "client_id": "uid456",
            "message_content": "Hello, this is a test message. The number is " + str(i)
        }
        test_app.put("/chats/uid456", json=body)

    response = test_app.get("/chats/uid123/uid456", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) == 5

    for i in range(5):
        assert messages[i]["message"] == "Hello, this is a test message. The number is " + str(i)

def test_search_messages(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("testuser0", "uid0", "Test User 0", "Test User 0", None, True, None, "2000-01-01")
    for i in range(1, 5):
        accounts_manager.insert("testuser" + str(i), "uid" + str(i), "Test User " + str(i), "test" + str(i) + "@example.com", None, False, None, "2000-01-01")

    for i in range(1, 5):
        body = {
            "provider_id": "uid0",
            "client_id": "uid" + str(i),
            "message_content": "Hello, this is a test message. The number is " + str(i)
        }
        assert test_app.put("/chats/uid0", json=body).status_code == 200
        
        body = {
            "provider_id": "uid0",
            "client_id": "uid" + str(i),
            "message_content": "Hello, this is a test message. The number is -" + str(i)
        }
        assert test_app.put("/chats/uid" + str(i), json=body).status_code == 200

    response = test_app.get("/chats/search", params={"limit": 100, "offset": 0})
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) == 8

def test_search_messages_client1(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("testuser0", "uid0", "Test User 0", "Test User 0", None, True, None, "2000-01-01")
    for i in range(1, 5):
        accounts_manager.insert("testuser" + str(i), "uid" + str(i), "Test User " + str(i), "test" + str(i) + "@example.com", None, False, None, "2000-01-01")

    for i in range(1, 5):
        body = {
            "provider_id": "uid0",
            "client_id": "uid" + str(i),
            "message_content": "Hello, this is a test message. The number is " + str(i)
        }
        assert test_app.put("/chats/uid0", json=body).status_code == 200
        
        body = {
            "provider_id": "uid0",
            "client_id": "uid" + str(i),
            "message_content": "Hello, this is a test message. The number is -" + str(i)
        }
        assert test_app.put("/chats/uid" + str(i), json=body).status_code == 200
    
    response = test_app.get("/chats/search", params={"client_id": "uid1", "limit": 100, "offset": 0})
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) == 2

def test_search_messages_sent_by_provider(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("testuser0", "uid0", "Test User 0", "Test User 0", None, True, None, "2000-01-01")
    for i in range(1, 5):
        accounts_manager.insert("testuser" + str(i), "uid" + str(i), "Test User " + str(i), "test" + str(i) + "@example.com", None, False, None, "2000-01-01")

    for i in range(1, 5):
        body = {
            "provider_id": "uid0",
            "client_id": "uid" + str(i),
            "message_content": "Hello, this is a test message. The number is " + str(i)
        }
        assert test_app.put("/chats/uid0", json=body).status_code == 200
        
        body = {
            "provider_id": "uid0",
            "client_id": "uid" + str(i),
            "message_content": "Hello, this is a test message. The number is -" + str(i)
        }
        assert test_app.put("/chats/uid" + str(i), json=body).status_code == 200
    
    response = test_app.get("/chats/search", params={"sender_id": "uid0", "limit": 100, "offset": 0})
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) == 4
    assert all([message["sender_id"] == "uid0" for message in messages])

def test_review_client(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    
    body = {"score": 4}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    updated_client = accounts_manager.get_by_username("clientuser")
    assert updated_client["client_count_score"] == 1
    assert updated_client["client_total_score"] == 4

def test_review_client_update(test_app, mocker):
    # Mock the database response
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    accounts_manager.insert("provideruser2", "uid_provider2", "Provider User 2", "provider2@example.com", None, True, None, "2000-01-01")

    body = {"score": 4}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    body = {"score": 2}
    response = test_app.put("/review/uid_client/uid_provider2", json=body)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    updated_client = accounts_manager.get_by_username("clientuser")
    assert updated_client["client_count_score"] == 2
    assert updated_client["client_total_score"] == 6

def test_review_client_missing_score(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    
    body = {}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing score"

def test_review_client_invalid_score(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    
    body = {"score": 6}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid score, must be between 0 and 5"

def test_review_client_extra_fields(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    
    body = {"score": 4, "extra_field": "extra_value"}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Extra fields:")

def test_review_client_not_found(test_app, mocker):
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    
    body = {"score": 4}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 404
    assert response.json()["detail"] == "Client user not found"

def test_review_provider_not_found(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    
    body = {"score": 4}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 404
    assert response.json()["detail"] == "Provider usernot found"

def test_review_client_not_a_client(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, True, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    
    body = {"score": 4}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 400
    assert response.json()["detail"] == "The user to be reviewed is not a client, something is wrong"

def test_review_provider_not_a_provider(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, False, None, "2000-01-01")
    
    body = {"score": 4}
    response = test_app.put("/review/uid_client/uid_provider", json=body)
    assert response.status_code == 400
    assert response.json()["detail"] == "The user who is reviewing is not a provider, something is wrong"

def test_add_favourite_provider(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    
    response = test_app.put("/favourites/add/uid_client/uid_provider")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_remove_favourite_provider(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    favourites_manager.add_favourite_provider("uid_client", "uid_provider")
    
    response = test_app.delete("/favourites/remove/uid_client/uid_provider")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_favourite_providers(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    accounts_manager.insert("provideruser", "uid_provider", "Provider User", "provider@example.com", None, True, None, "2000-01-01")
    favourites_manager.add_favourite_provider("uid_client", "uid_provider")
    
    response = test_app.get("/favourites/uid_client")
    assert response.status_code == 200
    providers = response.json()["providers"]
    assert len(providers) == 1
    assert providers[0] == "uid_provider"

def test_add_folder(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    
    response = test_app.put("/folders/add/uid_client/test_folder")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_remove_folder(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    favourites_manager.add_folder("uid_client", "test_folder")
    
    response = test_app.delete("/folders/remove/uid_client/test_folder")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_saved_folders(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    favourites_manager.add_folder("uid_client", "test_folder")
    
    response = test_app.get("/folders/uid_client")
    assert response.status_code == 200
    folders = response.json()["folders"]
    assert len(folders) == 1
    assert folders[0] == "test_folder"

def test_add_service_to_folder(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    favourites_manager.add_folder("uid_client", "test_folder")
    
    response = test_app.put("/folders/addservice/uid_client/test_folder/service123")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_remove_service_from_folder(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    favourites_manager.add_folder("uid_client", "test_folder")
    favourites_manager.add_service_to_folder("uid_client", "test_folder", "service123")
    
    response = test_app.delete("/folders/removeservice/uid_client/test_folder/service123")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_folder(test_app, mocker):
    accounts_manager.insert("clientuser", "uid_client", "Client User", "client@example.com", None, False, None, "2000-01-01")
    favourites_manager.add_folder("uid_client", "test_folder")
    favourites_manager.add_service_to_folder("uid_client", "test_folder", "service123")
    
    response = test_app.get("/folders/uid_client/test_folder")
    assert response.status_code == 200
    services = response.json()["services"]
    assert len(services) == 1
    assert services[0] == "service123"


