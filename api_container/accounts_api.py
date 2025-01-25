import datetime
from typing import Optional

import mongomock
from lib.utils import is_valid_date, time_to_string, get_test_engine, validate_location
from lib.rev2 import Rev2Graph
from lib.interest_prediction import InterestPrediction
from accounts_sql import Accounts
from chats_nosql import Chats
from favourites_nosql import Favourites
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
from imported_lib.ServicesService.services_lib import ServicesLib
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
    favourites_manager = Favourites(test_client=client)
    services_lib = ServicesLib(test_client=client)
else:
    firebase_manager = FirebaseManager()
    accounts_manager = Accounts()
    chats_manager = Chats()
    favourites_manager = Favourites()
    services_lib = ServicesLib()

REQUIRED_LOCATION_FIELDS = {"longitude", "latitude"}
REQUIRED_CREATE_FIELDS = {"username", "password",
                          "complete_name", "email", "is_provider", "birth_date"}
OPTIONAL_CREATE_FIELDS = {"profile_picture", "description"}
VALID_UPDATE_FIELDS = {"complete_name", "email",
                       "profile_picture", "description", "birth_date", "validated"}
ONLY_CLIENT_VALID_UPPDATE_FIELDS = {"reviewer_score", "client_count_score", "client_total_score"}
REQUIREDPASSWORDRESET_FIELDS = {"email"}
REQUIRED_SEND_MESSAGE_FIELDS = {"provider_id", "client_id", "message_content"}
PROVIDER_RANKINGS = {5: "great", 4: "good", 3: "just_ok", 2: "neutral", 1: "not_recommended", 0: "newbie"}
PROVIDER_RANKINGS_METRICS = {5: {"min_avg_rating": 0.9, "min_finished_percent": 0.8}, \
                                4: {"min_avg_rating": 0.75, "min_finished_percent": 0.7}, \
                                3: {"min_avg_rating": 0.6, "min_finished_percent": 0.6}, \
                                2: {"min_avg_rating": 0.4, "min_finished_percent": 0.0}, \
                                1: {"min_avg_rating": 0.0, "min_finished_percent": 0.0}}
MIN_FINISHED_RENTALS = 100
MAX_RATING = 5

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

@app.get("/rankings/{provider_id}")
def get_rankings(provider_id: str):
    account = accounts_manager.get(provider_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not account["is_provider"]:
        raise HTTPException(status_code=400, detail="Account is not a provider")
    
    total_rentals = services_lib.total_rentals(provider_id)
    finished_rentals = services_lib.finished_rentals(provider_id)
    finished_percent = finished_rentals / total_rentals if total_rentals > 0 else 0
    rating_metrics = services_lib.avg_rating(provider_id)

    avg_rating = rating_metrics["avg_rating"] if rating_metrics else None
    num_ratings = rating_metrics["num_ratings"] if rating_metrics else 0

    metrics = {"total_rentals": total_rentals, "finished_rentals": finished_rentals, "finished_percent": finished_percent, "avg_rating": avg_rating, "num_ratings": num_ratings}

    if finished_rentals < MIN_FINISHED_RENTALS or avg_rating is None:
        return {"status": "ok", "rank": PROVIDER_RANKINGS[0], "metrics": metrics}
    
    for i in range(MAX_RATING, -1, -1):
        min_avg_rating = PROVIDER_RANKINGS_METRICS[i]["min_avg_rating"] * MAX_RATING
        min_finished_percent = PROVIDER_RANKINGS_METRICS[i]["min_finished_percent"]
        if avg_rating >= min_avg_rating and finished_percent >= min_finished_percent:
            return {"status": "ok", "rank": PROVIDER_RANKINGS[i], "metrics": metrics}
        
@app.put("/review/{client_id}/{provider_id}")
def review_client(client_id: str, provider_id: str, body: dict):
    score = body.get("score")
    if score is None:
        raise HTTPException(status_code=400, detail="Missing score")
    extra_fields = set(body.keys()) - {"score"}
    if extra_fields:
        raise HTTPException(status_code=400, detail=f"""Extra fields: {
                            ', '.join(extra_fields)}""")
    
    client = accounts_manager.get(client_id)
    provider = accounts_manager.get(provider_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if not provider:
        raise HTTPException(status_code=404, detail="Provider usernot found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to be reviewed is not a client, something is wrong")
    if not provider["is_provider"]:
        raise HTTPException(status_code=400, detail="The user who is reviewing is not a provider, something is wrong")
    
    if type(score) == str:
        try:
            score = int(score)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid score")
    if score < 0 or score > MAX_RATING:
        raise HTTPException(status_code=400, detail="Invalid score, must be between 0 and 5")
    
    new_client_count_score = (client["client_count_score"] or 0) + 1
    new_client_total_score = (client["client_total_score"] or 0) + score
    if not accounts_manager.update(client["username"], {"client_count_score": new_client_count_score, "client_total_score": new_client_total_score}):
        raise HTTPException(status_code=400, detail="Error updating client")
    return {"status": "ok"}

@app.get("/fairness") # TODO: make this run in the background automatically
def get_fairness():
    edge_list = services_lib.get_recent_ratings(max_delta_days=360)
    # edge_list = _mocked_list()
    if not edge_list:
        raise HTTPException(status_code=404, detail="No ratings found")
    graph = Rev2Graph(edge_list)
    results = graph.get_results()
    return {"status": "ok", "results": results}

@app.put("/favourites/add/{client_id}/{provider_id}")
def add_favourite_provider(client_id: str, provider_id: str):
    client = accounts_manager.get(client_id)
    provider = accounts_manager.get(provider_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to add to favourites is not a client, something is wrong")
    if not provider:
        raise HTTPException(status_code=404, detail="Provider user not found")
    if not provider["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to add to favourites is not a provider, something is wrong")
    
    if not favourites_manager.add_favourite_provider(client_id, provider_id):
        raise HTTPException(status_code=400, detail="Error adding favourite provider")
    return {"status": "ok"}

@app.delete("/favourites/remove/{client_id}/{provider_id}")
def remove_favourite_provider(client_id: str, provider_id: str):
    client = accounts_manager.get(client_id)
    provider = accounts_manager.get(provider_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to remove from favourites is not a client, something is wrong")
    if not provider:
        raise HTTPException(status_code=404, detail="Provider user not found")
    if not provider["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to remove from favourites is not a provider, something is wrong")
    
    if not favourites_manager.remove_favourite_provider(client_id, provider_id):
        raise HTTPException(status_code=400, detail="Error removing favourite provider")
    return {"status": "ok"}

@app.get("/favourites/{client_id}")
def get_favourite_providers(client_id: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to get favourites is not a client, something is wrong")
    
    providers = favourites_manager.get_favourite_providers(client_id)
    if providers is None:
        raise HTTPException(status_code=404, detail="Client does not have any favourite providers")
    return {"status": "ok", "providers": providers}

@app.put("/folders/add/{client_id}/{folder_name}")
def add_folder(client_id: str, folder_name: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to add a folder is not a client, something is wrong")
    
    if not favourites_manager.add_folder(client_id, folder_name):
        raise HTTPException(status_code=400, detail="Error adding folder")
    return {"status": "ok"}

@app.delete("/folders/remove/{client_id}/{folder_name}")
def remove_folder(client_id: str, folder_name: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to remove a folder is not a client, something is wrong")
    
    if not favourites_manager.remove_folder(client_id, folder_name):
        raise HTTPException(status_code=400, detail="Error removing folder")
    return {"status": "ok"}

@app.get("/folders/{client_id}")
def get_saved_folders(client_id: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to get folders is not a client, something is wrong")
    
    folders = favourites_manager.get_saved_folders(client_id)
    if folders is None:
        raise HTTPException(status_code=404, detail="Client does not have any folders")
    return {"status": "ok", "folders": folders}

@app.put("/folders/addservice/{client_id}/{folder_name}/{service_id}")
def add_service_to_folder(client_id: str, folder_name: str, service_id: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to add a service to a folder is not a client, something is wrong")
    
    if not favourites_manager.add_service_to_folder(client_id, folder_name, service_id):
        raise HTTPException(status_code=400, detail="Error adding service to folder")
    return {"status": "ok"}

@app.delete("/folders/removeservice/{client_id}/{folder_name}/{service_id}")
def remove_service_from_folder(client_id: str, folder_name: str, service_id: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to remove a service from a folder is not a client, something is wrong")
    
    if not favourites_manager.remove_service_from_folder(client_id, folder_name, service_id):
        raise HTTPException(status_code=400, detail="Error removing service from folder")
    return {"status": "ok"}

@app.get("/folders/{client_id}/{folder_name}")
def get_folder(client_id: str, folder_name: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user to get a folder is not a client, something is wrong")
    
    services = favourites_manager.get_folder_services(client_id, folder_name)
    if services is None:
        raise HTTPException(status_code=404, detail="Client does not have that folder")
    return {"status": "ok", "services": services}

@app.get("folders/{client_id}/{folder_name}/recommendations")
def get_folder_recommendations(
    client_id: str,
    folder_name: str,
    client_location: str = Query(...),
    ):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(status_code=400, detail="The user is not a client, something is wrong")
    if not client_location:
        raise HTTPException(status_code=400, detail="Client location is required")
    client_location = validate_location(client_location, REQUIRED_LOCATION_FIELDS)
    
    if not favourites_manager.folder_exists(client_id, folder_name):
        raise HTTPException(status_code=404, detail="Client does not have that folder")
    
    available_services = services_lib.get_available_services(client_location)
    if not available_services:
        raise HTTPException(status_code=404, detail="No available services in the area")
    
    relations_dict = favourites_manager.get_relations(available_services)
    if relations_dict is None:
        raise HTTPException(status_code=404, detail="No available services to recommend")
    
    relations = [(folder, saved_service) for folder, saved_services in relations_dict.items() for saved_service in saved_services]
    interest_predictor = InterestPrediction(relations, folder_name)
    recommendations = interest_predictor.get_interest_prediction()
    return {"status": "ok", "recommendations": recommendations}

