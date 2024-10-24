import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True, scope='module')
def mock_firebase_manager():
    with patch('firebase_admin.credentials.Certificate') as MockCertificate:
        MockCertificate.return_value = MagicMock()
        with patch('accounts_api.FirebaseManager') as MockFirebaseManager:
            with patch('lib.utils.get_engine') as MockGetEngine:
                MockGetEngine.return_value = MagicMock()
                yield MockFirebaseManager