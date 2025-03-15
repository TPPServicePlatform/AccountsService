import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from accounts_sql import Accounts

# Run with the following command:
# pytest AccountsService/api_container/tests/test_accounts_sql.py

# Set the TESTING environment variable
os.environ['TESTING'] = '1'

# Set a default DATABASE_URL for testing
os.environ['DATABASE_URL'] = 'sqlite:///test.db'

# Set a default MONGO_TEST_DB for testing
os.environ['MONGO_TEST_DB'] = 'test_db'

@pytest.fixture(scope='module')
def engine():
    engine = create_engine('sqlite:///:memory:')
    yield engine
    engine.dispose()

@pytest.fixture(scope='module')
def accounts(engine):
    return Accounts(engine=engine)

@pytest.fixture(scope='function')
def session(engine, accounts):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.execute(accounts.accounts.delete())
    session.commit()
    session.close()

@pytest.fixture(scope='function', autouse=True)
def setup_teardown(engine, accounts):
    # Setup: Clear the database before each test
    accounts.accounts.drop(engine)
    accounts.accounts.create(engine)
    yield
    # Teardown: Clear the database after each test
    accounts.accounts.drop(engine)
    accounts.accounts.create(engine)

def test_insert(accounts):
    result = accounts.insert(
        username="testuser",
        uuid="1234",
        complete_name="Test User",
        email="testuser@example.com",
        profile_picture=None,
        is_provider=False,
        description="Test description",
        birth_date="2000-01-01"
    )
    assert result

def test_get(accounts):
    accounts.insert(
        username="testuser",
        uuid="1234",
        complete_name="Test User",
        email="testuser@example.com",
        profile_picture=None,
        is_provider=False,
        description="Test description",
        birth_date="2000-01-01"
    )
    account = accounts.get("1234")
    assert account is not None
    assert account['username'] == "testuser"
    assert account['uuid'] == "1234"
    assert account['complete_name'] == "Test User"
    assert account['email'] == "testuser@example.com"

def test_delete(accounts):
    accounts.insert(
        username="testuser",
        uuid="1234",
        complete_name="Test User",
        email="testuser@example.com",
        profile_picture=None,
        is_provider=False,
        description="Test description",
        birth_date="2000-01-01"
    )
    result = accounts.delete("testuser")
    assert result
    account = accounts.get("testuser")
    assert account is None

def test_update(accounts):
    accounts.insert(
        username="testuser",
        uuid="1234",
        complete_name="Test User",
        email="testuser@example.com",
        profile_picture=None,
        is_provider=False,
        description="Test description",
        birth_date="2000-01-01"
    )
    result = accounts.update("testuser", {"complete_name": "Updated User"})
    assert result
    account = accounts.get("1234")
    assert account['complete_name'] == "Updated User"

def test_rev2_results_saver(accounts):
    accounts.insert(
        username="testuser1",
        uuid="1234",
        complete_name="Test User 1",
        email="testuser1@example.com",
        profile_picture=None,
        is_provider=False,
        description="Test description 1",
        birth_date="2000-01-01"
    )
    accounts.insert(
        username="testuser2",
        uuid="5678",
        complete_name="Test User 2",
        email="testuser2@example.com",
        profile_picture=None,
        is_provider=False,
        description="Test description 2",
        birth_date="2000-02-02"
    )
    results = {
        "1234": 0.8,
        "5678": 0.9
    }
    accounts.rev2_results_saver(results)
    account1 = accounts.get("1234")
    account2 = accounts.get("5678")
    assert account1['reviewer_score'] == 0.8
    assert account2['reviewer_score'] == 0.9
