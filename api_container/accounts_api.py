from accounts_sql import Accounts
import logging as logger
import time
from firebase_manager import FirebaseManager
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from lib.utils import *
import sys
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

firebase_manager = FirebaseManager()
sql_manager = Accounts()

REQUIRED_CREATE_FIELDS = ["username", "password", "complete_name", "email", "profile_picture", "is_provider"]

starting_duration = time_to_string(time.time() - time_start)
logger.info(f"Accounts API started in {starting_duration}")

@app.get("/{username}")
def get_account(username: str):
    """
    curl example to get an account:
    curl -X 'GET' 'http://localhost:8000/api/accounts/marco' --header 'Content-Type: application/json'
    """
    account = sql_manager.get(username)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@app.post("/create_account")
def create_account(body: dict):
    """
    curl example to create an account:
    curl -X 'POST' 'http://localhost:8000/api/accounts/create_account' --header 'Content-Type: application/json' --data-raw '{"username": "marco", "complete_name": "Marco Polo", "email": "marco@polo.com", "profile_picture": "https://cdn.britannica.com/53/194553-050-88A5AC72/Marco-Polo-Italian-portrait-woodcut.jpg", "is_provider": true}'
    """
    username = body.get("username")
    password = body.get("password")
    complete_name = body.get("complete_name")
    email = body.get("email")
    profile_picture = body.get("profile_picture")
    is_provider = body.get("is_provider")
    if None in [username, complete_name, email, profile_picture, is_provider]:
        missing_fields = [field for field in REQUIRED_CREATE_FIELDS if body.get(field) is None]
        raise HTTPException(status_code=400, detail=f"Missing fields: {missing_fields}")
    if not sql_manager.insert(username, complete_name, email, profile_picture, is_provider):
        raise HTTPException(status_code=400, detail="Account already exists")
    created_user = firebase_manager.create_user(email, password)
    return {"status": "ok"}

@app.delete("/{username}")
def delete_account(username: str):
    """
    curl example to delete an account:
    curl -X 'DELETE' 'http://localhost:8000/api/accounts/marco' --header 'Content-Type: application/json'
    """
    if not sql_manager.delete(username):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "ok"}

# @app.put("/{username}")
# def update_account(username: str, body: dict):
#     return {"message": "This method is not implemented yet"}
