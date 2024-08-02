from accounts_sql import Accounts
import logging as logger
import time
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from lib.utils import *
import sys

time_start = time.time()

logger.basicConfig(format='%(levelname)s: %(asctime)s - %(message)s', stream=sys.stdout, level=logger.INFO)
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
    # To complete
    "http://example.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sql_manager = Accounts()

starting_duration = time_to_string(time.time() - time_start)
logger.info(f"Accounts API started in {starting_duration}")

@app.get("/accounts/{username}")
def get_account(username: str):
    """
    curl example to get an account:
    curl -X 'GET' \
        'http://localhost:8000/api/accounts/marco' \
        -H 'accept: application/json'
    """
    account = sql_manager.get(username)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@app.post("/accounts")
def create_account(username: str, complete_name: str, email: str, profile_picture: str, is_provider: bool):
    """
    curl example to create an account:
    curl -X 'POST' \
        'http://localhost:8000/api/accounts' \
        -H 'accept: application/json' \
        -H 'Content-Type: application/json' \
        -d '{
        "username": "marco",
        "complete_name": "Marco Polo",
        "email": marco@polo.com,
        "profile_picture": "https://cdn.britannica.com/53/194553-050-88A5AC72/Marco-Polo-Italian-portrait-woodcut.jpg",
        "is_provider": true
    }'
    """
    sql_manager.insert(username, complete_name, email, profile_picture, is_provider)
    return {"status": "ok"}

@app.delete("/accounts/{username}")
def delete_account(username: str):
    """
    curl example to delete an account:
    curl -X 'DELETE' \
        'http://localhost:8000/api/accounts/marco' \
        -H 'accept: application/json'
    """
    if not sql_manager.delete(username):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "ok"}