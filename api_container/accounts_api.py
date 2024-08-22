from accounts_sql import Accounts
import logging as logger
import time
from firebase_manager import FirebaseManager
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import sys
import firebase_admin
from firebase_admin.exceptions import FirebaseError
from firebase_admin import credentials, auth
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from lib.utils import time_to_string, get_test_engine

time_start = time.time()

logger.basicConfig(format='%(levelname)s: %(asctime)s - %(message)s',
                   stream=sys.stdout, level=logger.INFO)
logger.info("Starting the app")
load_dotenv()

DEBUG_MODE = os.getenv("DEBUG_MODE").title() == "True"
if DEBUG_MODE:
    logger.getLogger().setLevel(logger.DEBUG)
logger.info("DEBUG_MODE: " + str(DEBUG_MODE))

app = FastAPI(
    title="Accounts API",
    description="API for accounts management",
    version="1.0.0",
    root_path=os.getenv("ROOT_PATH")
)

origins = [
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.getenv('TESTING'):
    from unittest.mock import MagicMock
    firebase_manager = MagicMock()
    test_engine = get_test_engine()
    sql_manager = Accounts(engine=test_engine)
else:
    firebase_manager = FirebaseManager()
    sql_manager = Accounts()

REQUIRED_CREATE_FIELDS = {"username", "password", "complete_name", "email", "is_provider", "birth_date"}
OPTIONAL_CREATE_FIELDS = {"profile_picture", "description"}
VALID_UPDATE_FIELDS = {"complete_name", "email", "profile_picture", "description", "birth_date"}

starting_duration = time_to_string(time.time() - time_start)
logger.info(f"Accounts API started in {starting_duration}")

# TODO: (General) -> Create tests for each endpoint && add the required checks in each endpoint

@app.get("/{username}")
def get(username: str):
    account = sql_manager.get(username)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Account '{username}' not found")
    return account

@app.post("/create")
def create(body: dict):
    data = {key: value for key, value in body.items() if key in REQUIRED_CREATE_FIELDS or key in OPTIONAL_CREATE_FIELDS}
    
    if not all([field in data for field in REQUIRED_CREATE_FIELDS]):
        missing_fields = REQUIRED_CREATE_FIELDS - set(data.keys())
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing_fields)}")
    
    data.update({field: None for field in OPTIONAL_CREATE_FIELDS if field not in data})

    try:
        created_user = firebase_manager.create_user(data["email"], data["password"])
        if created_user is None:
            raise HTTPException(
                status_code=400, detail="Account already exists")

        if not sql_manager.insert(data["username"], created_user.uid, data["complete_name"], data["email"], data["profile_picture"], data["is_provider"], data["description"], data["birth_date"]):
            raise HTTPException(status_code=400, detail="Account already exists")
        
        return {"status": "ok", "user_id": f"{created_user.uid}"}
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Account already exists")
    except auth.FirebaseError as e:
        # print('Error creating user:', e)
        raise HTTPException(status_code=400, detail="Error creating user")
        

@app.delete("/{username}")
def delete(username: str):
    if not sql_manager.delete(username):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "ok"}

@app.put("/{username}")
def update(username: str, body: dict):
    update = {key: value for key, value in body.items() if key in VALID_UPDATE_FIELDS}
    if "validated" in body and body["validated"]:
        update["validated"] = True
    
    not_valid = {key for key in body if key not in update}
    if not_valid:
        raise HTTPException(status_code=400, detail=f"This fields does not exist or are not allowed to update: {', '.join(not_valid)}")

    if not sql_manager.get(username):
        raise HTTPException(status_code=404, detail="Account not found")
    
    if "password" in update:
        firebase_manager.update_password(username, update["password"])
    
    if not sql_manager.update(username, update):
        raise HTTPException(status_code=400, detail="Error updating account")
    return {"status": "ok"}
