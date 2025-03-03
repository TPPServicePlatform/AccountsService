import datetime
import os
import time
from typing import Optional, Union
import uuid
from sqlalchemy import create_engine
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import logging as logger
from fastapi import HTTPException
import re
import sentry_sdk

HOUR = 60 * 60
MINUTE = 60
MILLISECOND = 1_000

def time_to_string(time_in_seconds: float) -> str:
    minutes = int(time_in_seconds // MINUTE)
    seconds = int(time_in_seconds % MINUTE)
    millis = int((time_in_seconds - int(time_in_seconds)) * MILLISECOND)
    return f"{minutes}m {seconds}s {millis}ms"

def get_engine() -> Optional[create_engine]:
    return create_engine(
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}",
        echo=True
    )

def get_test_engine():
    database_url = os.getenv('DATABASE_URL', 'sqlite:///test.db')  # Default to a SQLite database for testing
    return create_engine(database_url)

def get_mongo_client() -> MongoClient:
    if not all([os.getenv('MONGO_USER'), os.getenv('MONGO_PASSWORD'), os.getenv('MONGO_HOST'), os.getenv('MONGO_APP_NAME')]):
        raise HTTPException(status_code=500, detail="MongoDB environment variables are not set properly")
    uri = f"mongodb+srv://{os.getenv('MONGO_USER')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}/?retryWrites=true&w=majority&appName={os.getenv('MONGO_APP_NAME')}"
    print(f"Connecting to MongoDB: {uri}")
    logger.getLogger('pymongo').setLevel(logger.WARNING)
    return MongoClient(uri, server_api=ServerApi('1'))

def get_actual_time() -> str:
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

def is_valid_date(date: str):
    try:
        datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return False
    return True

def is_float(value):
    float_pattern = re.compile(r'^-?\d+(\.\d+)?$')
    return bool(float_pattern.match(value))

def validate_location(client_location, required_fields):
    if type(client_location) == str:
        if client_location.count(",") != 1:
            raise HTTPException(status_code=400, detail="Invalid client location (must be in the format 'longitude,latitude')")
        client_location = client_location.split(",")
        client_location = {"longitude": client_location[0], "latitude": client_location[1]}
    elif type(client_location) == dict:
        if not all([field in client_location for field in required_fields]):
            missing_fields = required_fields - set(client_location.keys())
            raise HTTPException(status_code=400, detail=f"Missing location fields: {', '.join(missing_fields)}")
    else:
        raise HTTPException(status_code=400, detail="Invalid client location (must be a string or a dictionary)")
    if not all([type(value) in [int, float] or is_float(value) for value in client_location.values()]):
        raise HTTPException(status_code=400, detail="Invalid client location (each value must be a float)")
    client_location = {key: float(value) for key, value in client_location.items()}
    return client_location

def validate_identity():
    # Add here a third party service to validate the identity of the user
    return True

def save_file(provider_id: str, _file: Union[bytes, str]) -> str:
    # Add here a third party service to save the file (e.g. AWS S3)
    return f"mocked/third_party/storage/{provider_id}/{uuid.uuid4()}.pdf"

def get_file(file_path: str) -> bytes:
    # Add here a third party service to get the file (e.g. AWS S3)
    # TODO: put an example pdf
    return b"mocked/file"

def delete_file(file_path: str):
    # Add here a third party service to delete the file (e.g. AWS S3)
    pass

def sentry_init():
    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for tracing.
        traces_sample_rate=1.0,
        _experiments={
            # Set continuous_profiling_auto_start to True
            # to automatically start the profiler on when
            # possible.
            "continuous_profiling_auto_start": True,
        },
    )
    