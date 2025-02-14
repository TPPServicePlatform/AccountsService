import pytest
import mongomock
from unittest.mock import patch
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from chats_nosql import Chats

# Run with the following command:
# pytest AccountsService/api_container/tests/test_chats_nosql.py

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
def chats(mongo_client):
    return Chats(test_client=mongo_client)

def test_insert_message(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    chat_id = chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    assert chat_id is not None

def test_insert_message_existing_chat(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    chat_id_1 = chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    assert chat_id_1 is not None
    chat_id_2 = chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Another test message.',
        message_sender_id='client_1'
    )
    assert chat_id_2 is not None
    assert chat_id_1 == chat_id_2

def test_get_messages(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    chat_id = chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    messages = chats.get_messages(provider_id='provider_1', client_id='client_1', limit=10, offset=0)
    assert messages is not None
    assert len(messages) == 1
    assert messages[0]['message'] == 'Hello, this is a test message.'

def test_get_multiple_messages(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    _ = chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    _ = chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Another test message.',
        message_sender_id='client_1'
    )
    messages = chats.get_messages(provider_id='provider_1', client_id='client_1', limit=10, offset=0)
    assert messages is not None
    assert len(messages) == 2
    assert messages[0]['message'] in ['Hello, this is a test message.', 'Another test message.']
    assert messages[1]['message'] in ['Hello, this is a test message.', 'Another test message.']
    assert messages[0]['message'] != messages[1]['message']

def test_delete_chat(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    chat_id = chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    result = chats.delete(chat_id)
    assert result is True
    messages = chats.get_messages(provider_id='provider_1', client_id='client_1', limit=10, offset=0)
    assert messages is None

def test_count_messages(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    count = chats.count_messages(provider_id='provider_1', client_id='client_1')
    assert count == 1

def test_count_multiple_messages(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Another test message.',
        message_sender_id='client_1'
    )
    count = chats.count_messages(provider_id='provider_1', client_id='client_1')
    assert count == 2

def test_search_messages(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    chats.insert_message(
        provider_id='provider_1',
        client_id='client_2',
        message_content='Another test message.',
        message_sender_id='client_1'
    )
    results = chats.search(limit=10, offset=0, provider_id='provider_1', client_id='client_1')
    assert results is not None
    assert len(results) == 1
    assert results[0]['message'] == 'Hello, this is a test message.'

def test_search_multiple_messages(chats, mocker):
    mocker.patch('chats_nosql.get_actual_time', return_value=1672531200)  # 2023-01-01 00:00:00
    chats.insert_message(
        provider_id='provider_1',
        client_id='client_1',
        message_content='Hello, this is a test message.',
        message_sender_id='provider_1'
    )
    chats.insert_message(
        provider_id='provider_1',
        client_id='client_2',
        message_content='Another test message.',
        message_sender_id='client_1'
    )
    results = chats.search(limit=10, offset=0, provider_id='provider_1')
    assert results is not None
    assert len(results) == 2
    assert 'Hello, this is a test message.' in [result['message'] for result in results]
    assert 'Another test message.' in [result['message'] for result in results]