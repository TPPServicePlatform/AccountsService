import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from accounts_sql import Accounts

class TestAccounts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite:///:memory:')
        cls.Session = sessionmaker(bind=cls.engine)
        cls.accounts = Accounts(engine=cls.engine)  # Inject the test engine

    def setUp(self):
        self.session = self.Session()

    def tearDown(self):
        self.session.execute(self.accounts.accounts.delete())
        self.session.commit()
        self.session.close()

    def test_insert(self):
        result = self.accounts.insert(
            username="testuser",
            uuid="1234",
            complete_name="Test User",
            email="testuser@example.com",
            profile_picture=None,
            is_provider=False,
            description="Test description",
            birth_date="2000-01-01"
        )
        self.assertTrue(result)

    def test_get(self):
        self.accounts.insert(
            username="testuser",
            uuid="1234",
            complete_name="Test User",
            email="testuser@example.com",
            profile_picture=None,
            is_provider=False,
            description="Test description",
            birth_date="2000-01-01"
        )
        account = self.accounts.get("testuser")
        self.assertIsNotNone(account)
        self.assertEqual(account['username'], "testuser")

    def test_delete(self):
        self.accounts.insert(
            username="testuser",
            uuid="1234",
            complete_name="Test User",
            email="testuser@example.com",
            profile_picture=None,
            is_provider=False,
            description="Test description",
            birth_date="2000-01-01"
        )
        result = self.accounts.delete("testuser")
        self.assertTrue(result)
        account = self.accounts.get("testuser")
        self.assertIsNone(account)

    def test_update(self):
        self.accounts.insert(
            username="testuser",
            uuid="1234",
            complete_name="Test User",
            email="testuser@example.com",
            profile_picture=None,
            is_provider=False,
            description="Test description",
            birth_date="2000-01-01"
        )
        result = self.accounts.update("testuser", {"complete_name": "Updated User"})
        self.assertTrue(result)
        account = self.accounts.get("testuser")
        self.assertEqual(account['complete_name'], "Updated User")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

if __name__ == '__main__':
    unittest.main()
