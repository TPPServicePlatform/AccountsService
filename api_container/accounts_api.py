import datetime
from typing import Optional

import mongomock
from lib.utils import is_valid_date, time_to_string, get_test_engine
from accounts_sql import Accounts
from chats_nosql import Chats
import logging as logger
import time
from firebase_manager import FirebaseManager
from fastapi import FastAPI, File, Query, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import sys
import firebase_admin
from firebase_admin.exceptions import FirebaseError
from firebase_admin import credentials, auth
import os

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'lib')))

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
    accounts_manager = Accounts(engine=test_engine)

    client = mongomock.MongoClient()
    chats_manager = Chats(test_client=client)
else:
    firebase_manager = FirebaseManager()
    accounts_manager = Accounts()
    chats_manager = Chats()

REQUIRED_CREATE_FIELDS = {"username", "password",
                          "complete_name", "email", "is_provider", "birth_date"}
OPTIONAL_CREATE_FIELDS = {"profile_picture", "description"}
VALID_UPDATE_FIELDS = {"complete_name", "email",
                       "profile_picture", "description", "birth_date"}
REQUIREDPASSWORDRESET_FIELDS = {"email"}
REQUIRED_SEND_MESSAGE_FIELDS = {"provider_id", "client_id", "message_content"}

starting_duration = time_to_string(time.time() - time_start)
logger.info(f"Accounts API started in {starting_duration}")

# TODO: (General) -> Create tests for each endpoint && add the required checks in each endpoint


@app.get("/get/{username}")
def get(username: str):
    account = accounts_manager.get_by_username(username)
    if account is None:
        raise HTTPException(status_code=404, detail=f"""Account '{
                            username}' not found""")
    return account


@app.post("/create")
def create(body: dict):
    data = {key: value for key, value in body.items(
    ) if key in REQUIRED_CREATE_FIELDS or key in OPTIONAL_CREATE_FIELDS}

    if not all([field in data for field in REQUIRED_CREATE_FIELDS]):
        missing_fields = REQUIRED_CREATE_FIELDS - set(data.keys())
        raise HTTPException(status_code=400, detail=f"""Missing fields: {
                            ', '.join(missing_fields)}""")

    data.update(
        {field: None for field in OPTIONAL_CREATE_FIELDS if field not in data})

    try:
        created_user = firebase_manager.create_user(
            data["email"], data["password"])
        if created_user is None:
            raise HTTPException(
                status_code=400, detail="Account already exists")

        if not accounts_manager.insert(data["username"], created_user.uid, data["complete_name"], data["email"], data["profile_picture"], data["is_provider"], data["description"], data["birth_date"]):
            raise HTTPException(
                status_code=400, detail="Account already exists")

        return {"status": "ok", "user_id": f"{created_user.uid}"}
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Account already exists")
    except auth.FirebaseError as e:
        # print('Error creating user:', e)
        raise HTTPException(status_code=400, detail="Error creating user")


@app.delete("/delete/{username}")
def delete(username: str):
    if not accounts_manager.delete(username):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "ok"}


@app.put("/update/{username}")
def update(username: str, body: dict):
    update = {key: value for key,
              value in body.items() if key in VALID_UPDATE_FIELDS}
    if "validated" in body and body["validated"]:
        update["validated"] = True

    not_valid = {key for key in body if key not in update}
    if not_valid:
        raise HTTPException(status_code=400, detail=f"""This fields does not exist or are not allowed to update: {
                            ', '.join(not_valid)}""")

    if not accounts_manager.get_by_username(username):
        raise HTTPException(status_code=404, detail="Account not found")

    if "password" in update:
        firebase_manager.update_password(username, update["password"])

    if not accounts_manager.update(username, update):
        raise HTTPException(status_code=400, detail="Error updating account")
    return {"status": "ok"}


@app.post("/passwordreset")
def password_reset(body: dict):
    data = {key: value for key, value in body.items(
    ) if key in REQUIREDPASSWORDRESET_FIELDS}

    if not accounts_manager.getemail(data["email"]):
        raise HTTPException(status_code=404, detail="Account not found")

    firebase_manager.password_reset(data["email"])
    return {"status": "ok"}


@app.put("/chats/{destination_id}")
def send_message(destination_id: str, body: dict):
    data = {key: value for key, value in body.items() if key in REQUIRED_SEND_MESSAGE_FIELDS}

    if not all([field in data for field in REQUIRED_SEND_MESSAGE_FIELDS]):
        missing_fields = REQUIRED_SEND_MESSAGE_FIELDS - set(data.keys())
        raise HTTPException(status_code=400, detail=f"""Missing fields: {
                            ', '.join(missing_fields)}""")
    
    extra_fields = set(data.keys()) - REQUIRED_SEND_MESSAGE_FIELDS
    if extra_fields:
        raise HTTPException(status_code=400, detail=f"""Extra fields: {
                            ', '.join(extra_fields)}""")
    
    if not destination_id in {data["provider_id"], data["client_id"]}:
        raise HTTPException(status_code=400, detail="Destination ID does not match with provider_id or client_id")
    
    if not accounts_manager.get(data["provider_id"]):
        raise HTTPException(status_code=404, detail="Provider not found")
    if not accounts_manager.get(data["client_id"]):
        raise HTTPException(status_code=404, detail="Client not found")
    
    sender_id = ({data["provider_id"], data["client_id"]} - {destination_id}).pop()
    chat_id = chats_manager.insert_message(data["provider_id"], data["client_id"], data["message_content"], sender_id)
    if chat_id is None:
        raise HTTPException(status_code=400, detail="Error inserting message")
    return {"status": "ok", "chat_id": chat_id}

@app.get("/chats/{provider_id}/{client_id}")
def get_chat(provider_id: str, client_id: str, limit: int, offset: int):
    if not accounts_manager.get(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    if not accounts_manager.get(client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    
    messages = chats_manager.get_messages(provider_id, client_id, limit, offset)
    if messages is None:
        raise HTTPException(status_code=404, detail="No messages found")
    return {"status": "ok", "messages": messages}

@app.get("/chats/search")
def search_messages(
    limit: int = Query(...),
    offset: int = Query(...),
    provider_id: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    sender_id: Optional[str] = Query(None),
    min_date: Optional[str] = Query(None),
    max_date: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None)
):
    if provider_id is not None and not accounts_manager.get(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    if client_id is not None and not accounts_manager.get(client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    if sender_id is not None and not accounts_manager.get(sender_id):
        raise HTTPException(status_code=404, detail="Sender not found")
    
    if keywords is not None:
        keywords = keywords.split()
    
    if min_date is not None and not is_valid_date(min_date):
        raise HTTPException(status_code=400, detail="Invalid min_date")
    if max_date is not None and not is_valid_date(max_date):
        raise HTTPException(status_code=400, detail="Invalid max_date")
    
    messages = chats_manager.search(limit, offset, provider_id, client_id, sender_id, min_date, max_date, keywords)
    if messages is None:
        raise HTTPException(status_code=404, detail="No messages found")
    return {"status": "ok", "messages": messages}
