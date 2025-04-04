from fastapi import Form, UploadFile, File
import base64
import datetime
from typing import Optional

import mongomock
from lib.utils import get_file, is_valid_date, save_file, sentry_init, time_to_string, get_test_engine, validate_identity, validate_location
# from lib.rev2 import Rev2Graph
from lib.new_rev2 import Rev2Graph, rev2_calculator
from lib.interest_prediction import InterestPredictor
from accounts_sql import Accounts
from chats_nosql import Chats
from favourites_nosql import Favourites
from certificates_nosql import Certificates
from mobile_token_nosql import MobileToken, send_notification
import logging as logger
import time
from firebase_manager import FirebaseManager
from fastapi import FastAPI, File, Query, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import sys
import firebase_admin
from firebase_admin import credentials, auth, exceptions
from imported_lib.ServicesService.services_lib import ServicesLib
from imported_lib.SupportService.support_lib import SupportLib
from multiprocessing import Process

import os

time_start = time.time()

logger.basicConfig(format='%(levelname)s: %(asctime)s - %(message)s',
                   stream=sys.stdout, level=logger.INFO)
logger.info("Starting the app")
load_dotenv()

DEBUG_MODE = os.getenv("DEBUG_MODE").title() == "True"
if DEBUG_MODE:
    logger.getLogger().setLevel(logger.DEBUG)
logger.info("DEBUG_MODE: " + str(DEBUG_MODE))

sentry_init()

app = FastAPI(
    title="Accounts API",
    description="API for accounts management",
    version="1.0.0",
    root_path=os.getenv("ROOT_PATH")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.getenv('TESTING'):
    from unittest.mock import MagicMock
    firebase_manager = FirebaseManager()
    test_engine = get_test_engine()
    accounts_manager = Accounts(engine=test_engine)

    client = mongomock.MongoClient()
    chats_manager = Chats(test_client=client)
    favourites_manager = Favourites(test_client=client)
    services_lib = ServicesLib(test_client=client)
    support_lib = SupportLib(test_client=client)
    certificates_manager = Certificates(test_client=client)
    mobile_token_manager = MobileToken(test_client=client)
else:
    firebase_manager = FirebaseManager()
    accounts_manager = Accounts()
    chats_manager = Chats()
    favourites_manager = Favourites()
    services_lib = ServicesLib()
    support_lib = SupportLib()
    certificates_manager = Certificates()
    mobile_token_manager = MobileToken()

    rev2_process = Process(target=rev2_calculator)

REQUIRED_LOCATION_FIELDS = {"longitude", "latitude"}
IDENTITY_VALIDATION_FIELDS = set()
REQUIRED_CREATE_FIELDS = {"username", "password",
                          "complete_name", "email", "is_provider", "birth_date"}
OPTIONAL_CREATE_FIELDS = {"profile_picture", "description"}
VALID_UPDATE_FIELDS = {"complete_name", "email",
                       "profile_picture", "description", "birth_date", "validated"}
ONLY_CLIENT_VALID_UPPDATE_FIELDS = {
    "reviewer_score", "client_count_score", "client_total_score"}
REQUIREDPASSWORDRESET_FIELDS = {"email"}
REQUIRED_SEND_MESSAGE_FIELDS = {"provider_id", "client_id", "message_content"}
PROVIDER_RANKINGS = {5: "great", 4: "good", 3: "just_ok",
                     2: "neutral", 1: "not_recommended", 0: "newbie"}
PROVIDER_RANKINGS_METRICS = {5: {"min_avg_rating": 0.9, "min_finished_percent": 0.8},
                             4: {"min_avg_rating": 0.75, "min_finished_percent": 0.7},
                             3: {"min_avg_rating": 0.6, "min_finished_percent": 0.6},
                             2: {"min_avg_rating": 0.4, "min_finished_percent": 0.0},
                             1: {"min_avg_rating": 0.0, "min_finished_percent": 0.0}}
MIN_FINISHED_RENTALS = 100
MAX_RATING = 5
REQUIRED_CERTIFICATE_FIELDS = {"name", "description"}
VALID_UPDATE_CERTIFICATE_FIELDS = {
    "name", "description", "path", "is_validated", "expiration_date"}

starting_duration = time_to_string(time.time() - time_start)
logger.info(f"Accounts API started in {starting_duration}")

# TODO: (General) -> Create tests for each endpoint && add the required checks in each endpoint


@app.get("/get/{username}")
def get(username: str):
    account = accounts_manager.get_by_username(username)
    if account is None:
        raise HTTPException(status_code=404, detail=f"""Account '{
                            username}' not found""")
    return {"status": "ok", "account": account, "suspension": support_lib.check_suspension(account["user_id"])}


@app.get("/notifications/get/{user_id}")
def get_notifications(user_id: str, delete_all: bool = False):
    notifications = mobile_token_manager.get_notifications(user_id, delete_all)
    if notifications is None:
        raise HTTPException(status_code=404, detail="Notifications not found")
    return {"status": "ok", "notifications": notifications}


@app.post("/login")
def login(body: dict):
    data = {key: value for key, value in body.items() if key in [
        "email", "password"]}
    if not all([field in data for field in ["email", "password"]]):
        missing_fields = ["email", "password"] - set(data.keys())
        raise HTTPException(status_code=400, detail=f"""Missing fields: {
                            ', '.join(missing_fields)}""")
    user = firebase_manager.login_user(data["email"], data["password"])
    if user is None:
        raise HTTPException(status_code=404, detail="Invalid credentials")
    suspended = support_lib.check_suspension(user.uid)
    if suspended:
        raise HTTPException(status_code=403, detail="User is suspended")
    return {"status": "ok", "user_id": f"{user.uid}"}


@app.get("/getemail/{email}")
def getemail(email: str):
    account = accounts_manager.getemail(email)
    if account is None:
        raise HTTPException(status_code=404, detail=f"""Account with email '{
                            email}' not found""")
    return account


@app.get("/getuid/{uid}")
def getuid(uid: str):
    account = accounts_manager.get(uid)
    if account is None:
        raise HTTPException(status_code=404, detail=f"""Account with uid '{
                            uid}' not found""")
    return account


@app.post("/verificationmail/{uid}")
def sendverification(uid: str):
    account = accounts_manager.get(uid)
    if account is None:
        raise HTTPException(
            status_code=404, detail=f"""Account with email not found""")
    try:
        firebase_manager.send_email_verification(account["email"])
    except exceptions.FirebaseError:
        raise HTTPException(
            status_code=400, detail="Error sending email verification")
    return {"status": "ok"}


@app.get("/isemailverified/{uid}")
def isemailverified(udi: str):
    return {"email_verified": firebase_manager.is_email_verified(uid)}


@app.post("/create")
def create(body: dict):
    data = {key: value for key, value in body.items(
    ) if key in REQUIRED_CREATE_FIELDS or key in OPTIONAL_CREATE_FIELDS}

    if not all([field in data for field in REQUIRED_CREATE_FIELDS]):
        missing_fields = REQUIRED_CREATE_FIELDS - set(data.keys())
        raise HTTPException(status_code=400, detail=f"""Missing fields: {
                            ', '.join(missing_fields)}""")

    if not validate_identity():
        raise HTTPException(
            status_code=400, detail="Identity validation failed")

    if "is_provider" in data:
        if isinstance(data["is_provider"], str):
            data["is_provider"] = data["is_provider"].lower() == "true"
    else:
        data["is_provider"] = False

    data.update(
        {field: None for field in OPTIONAL_CREATE_FIELDS if field not in data})

    try:
        if accounts_manager.get_by_username(data["username"]) is not None:
            raise HTTPException(
                status_code=400, detail="Username already exists")
        created_user = firebase_manager.create_user(
            data["email"], data["password"])
        if created_user is None:
            raise HTTPException(
                status_code=400, detail="Account already exists")

        if not accounts_manager.insert(data["username"], created_user.uid, data["complete_name"], data["email"], data["profile_picture"], data["is_provider"], data["description"], data["birth_date"]):
            firebase_manager.delete_user(created_user.uid)
            raise HTTPException(
                status_code=400, detail="Account already exists")

        return {"status": "ok", "user_id": f"{created_user.uid}"}
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Account already exists")
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=400, detail="Error creating user")


@app.put("/token/{user_id}")
def update_token(user_id: str, body: dict):
    if "mobile_token" not in body:
        raise HTTPException(status_code=400, detail="Missing mobile_token")
    extra_fields = set(body.keys()) - {"mobile_token"}
    if extra_fields:
        raise HTTPException(status_code=400, detail=f"""Extra fields: {
                            ', '.join(extra_fields)}""")
    mobile_token_manager.update_mobile_token(user_id, body["mobile_token"])
    return {"status": "ok"}


@app.put("verify/{uid}")
def verify(uid: str):
    user = accounts_manager.get(uid)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    firebase_manager.verify_email(user["email"])
    return {"status": "ok"}


@app.delete("/delete/{username}")
def delete(username: str):
    user = accounts_manager.get_by_username(username)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if not accounts_manager.delete(username):
        raise HTTPException(status_code=404, detail="Account not found")
    certificates_manager.delete_provider_certificates(user["uuid"])
    firebase_manager.delete_user(user["uuid"])
    return {"status": "ok"}


@app.delete("/deleteuid/{uid}")
def deleteuid(uid: str):
    user = accounts_manager.get(uid)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if not accounts_manager.delete(user["username"]):
        raise HTTPException(status_code=404, detail="Account not found")
    certificates_manager.delete_provider_certificates(user["uuid"])
    firebase_manager.delete_user(user["uuid"])
    return {"status": "ok"}


@app.put("/update/{username}")
def update(username: str, body: dict):
    update = {key: value for key,
              value in body.items() if key in VALID_UPDATE_FIELDS}
    if "validated" in body and body["validated"]:
        update["validated"] = True
    print(update)

    not_valid = {key for key in body if key not in update}
    print("not_valid", not_valid)
    if not_valid:
        raise HTTPException(status_code=400, detail=f"""This fields does not exist or are not allowed to update: {
                            ', '.join(not_valid)}""")

    if not accounts_manager.get_by_username(username):
        raise HTTPException(status_code=404, detail="Account not found")

    if "password" in update:
        firebase_manager.update_password(username, update["password"])

    if not accounts_manager.update(username, update):
        print("Error updating account")
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
    data = {key: value for key, value in body.items(
    ) if key in REQUIRED_SEND_MESSAGE_FIELDS}

    if not all([field in data for field in REQUIRED_SEND_MESSAGE_FIELDS]):
        missing_fields = REQUIRED_SEND_MESSAGE_FIELDS - set(data.keys())
        raise HTTPException(status_code=400, detail=f"""Missing fields: {
                            ', '.join(missing_fields)}""")

    extra_fields = set(data.keys()) - REQUIRED_SEND_MESSAGE_FIELDS
    if extra_fields:
        raise HTTPException(status_code=400, detail=f"""Extra fields: {
                            ', '.join(extra_fields)}""")

    if not destination_id in {data["provider_id"], data["client_id"]}:
        raise HTTPException(
            status_code=400, detail="Destination ID does not match with provider_id or client_id")

    if not accounts_manager.get(data["provider_id"]):
        raise HTTPException(status_code=404, detail="Provider not found")
    if not accounts_manager.get(data["client_id"]):
        raise HTTPException(status_code=404, detail="Client not found")

    sender_id_set = {data["provider_id"], data["client_id"]} - {destination_id}
    if len(sender_id_set) != 1:
        raise HTTPException(
            status_code=400, detail="Error determining sender, check your params")
    sender_id = sender_id_set.pop()
    chat_id = chats_manager.insert_message(
        data["provider_id"], data["client_id"], data["message_content"], sender_id)
    if chat_id is None:
        raise HTTPException(status_code=400, detail="Error inserting message")
    sender_user = accounts_manager.get(sender_id)["username"]
    send_notification(mobile_token_manager, destination_id,
                      f"New message from {sender_user}", data["message_content"])
    return {"status": "ok", "chat_id": chat_id}


@app.get("/chats/one/{provider_id}/{client_id}")
def get_chat(provider_id: str, client_id: str, limit: int, offset: int):
    if not accounts_manager.get(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    if not accounts_manager.get(client_id):
        raise HTTPException(status_code=404, detail="Client not found")

    messages = chats_manager.get_messages(
        provider_id, client_id, limit, offset)
    if messages is None:
        raise HTTPException(status_code=404, detail="No messages found")

    total_messages = chats_manager.count_messages(provider_id, client_id)
    return {"status": "ok", "messages": messages, "total_messages": total_messages}


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

    messages = chats_manager.search(
        limit, offset, provider_id, client_id, sender_id, min_date, max_date, keywords)
    if messages is None:
        raise HTTPException(status_code=404, detail="No messages found")
    return {"status": "ok", "messages": messages}


@app.get("/chats/all/{user_id}")
def get_all_chats(user_id: str, is_provider: bool):
    user = accounts_manager.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if is_provider and not user["is_provider"]:
        raise HTTPException(status_code=400, detail="User is not a provider")
    if not is_provider and user["is_provider"]:
        raise HTTPException(status_code=400, detail="User is not a client")
    all_chats = chats_manager.get_chats(user_id, is_provider)
    return {"status": "ok"} | all_chats


@app.get("/rankings/{provider_id}")
def get_rankings(provider_id: str):
    account = accounts_manager.get(provider_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not account["is_provider"]:
        raise HTTPException(
            status_code=400, detail="Account is not a provider")

    total_rentals = services_lib.total_rentals(provider_id)
    finished_rentals = services_lib.finished_rentals(provider_id)
    finished_percent = finished_rentals / total_rentals if total_rentals > 0 else 0
    rating_metrics = services_lib.avg_rating(provider_id)

    avg_rating = rating_metrics["avg_rating"] if rating_metrics else None
    num_ratings = rating_metrics["num_ratings"] if rating_metrics else 0

    metrics = {"total_rentals": total_rentals, "finished_rentals": finished_rentals,
               "finished_percent": finished_percent, "avg_rating": avg_rating, "num_ratings": num_ratings}

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
        raise HTTPException(
            status_code=400, detail="The user to be reviewed is not a client, something is wrong")
    if not provider["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user who is reviewing is not a provider, something is wrong")

    if type(score) == str:
        try:
            score = int(score)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid score")
    if score < 0 or score > MAX_RATING:
        raise HTTPException(
            status_code=400, detail="Invalid score, must be between 0 and 5")

    new_client_count_score = (client["client_count_score"] or 0) + 1
    new_client_total_score = (client["client_total_score"] or 0) + score
    if not accounts_manager.update(client["username"], {"client_count_score": new_client_count_score, "client_total_score": new_client_total_score}):
        raise HTTPException(status_code=400, detail="Error updating client")
    return {"status": "ok"}


@app.get("/fairness")  # TODO: make this run in the background automatically
def get_fairness():
    edge_list = services_lib.get_recent_ratings(max_delta_days=360)
    if not edge_list:
        raise HTTPException(status_code=404, detail="No ratings found")
    graph = Rev2Graph(edge_list)
    results: dict = graph.calculate()
    results = {key[1:]: value for key, value in results.items()}
    #sort the dict
    results = dict(sorted(results.items(), key=lambda item: item[1], reverse=True))
    return {"status": "ok", "results": results}


@app.put("/favourites/add/{client_id}/{provider_id}")
def add_favourite_provider(client_id: str, provider_id: str):
    client = accounts_manager.get(client_id)
    provider = accounts_manager.get(provider_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to add to favourites is not a client, something is wrong")
    if not provider:
        raise HTTPException(status_code=404, detail="Provider user not found")
    if not provider["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to add to favourites is not a provider, something is wrong")

    if not favourites_manager.add_favourite_provider(client_id, provider_id):
        raise HTTPException(
            status_code=400, detail="Error adding favourite provider")
    return {"status": "ok"}


@app.delete("/favourites/remove/{client_id}/{provider_id}")
def remove_favourite_provider(client_id: str, provider_id: str):
    client = accounts_manager.get(client_id)
    provider = accounts_manager.get(provider_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to remove from favourites is not a client, something is wrong")
    if not provider:
        raise HTTPException(status_code=404, detail="Provider user not found")
    if not provider["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to remove from favourites is not a provider, something is wrong")

    if not favourites_manager.remove_favourite_provider(client_id, provider_id):
        raise HTTPException(
            status_code=400, detail="Error removing favourite provider")
    return {"status": "ok"}


@app.get("/favourites/{client_id}")
def get_favourite_providers(client_id: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to get favourites is not a client, something is wrong")

    providers = favourites_manager.get_favourite_providers(client_id)
    if providers is None:
        raise HTTPException(
            status_code=404, detail="Client does not have any favourite providers")
    return {"status": "ok", "providers": providers}


@app.put("/folders/add/{client_id}/{folder_name}")
def add_folder(client_id: str, folder_name: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to add a folder is not a client, something is wrong")

    if not favourites_manager.add_folder(client_id, folder_name):
        raise HTTPException(status_code=400, detail="Error adding folder")
    return {"status": "ok"}


@app.delete("/folders/remove/{client_id}/{folder_name}")
def remove_folder(client_id: str, folder_name: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to remove a folder is not a client, something is wrong")

    if not favourites_manager.remove_folder(client_id, folder_name):
        raise HTTPException(status_code=400, detail="Error removing folder")
    return {"status": "ok"}


@app.get("/folders/{client_id}")
def get_saved_folders(client_id: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to get folders is not a client, something is wrong")

    folders = favourites_manager.get_saved_folders(client_id)
    if folders is None:
        raise HTTPException(
            status_code=404, detail="Client does not have any folders")
    return {"status": "ok", "folders": folders}


@app.put("/folders/addservice/{client_id}/{folder_name}/{service_id}")
def add_service_to_folder(client_id: str, folder_name: str, service_id: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to add a service to a folder is not a client, something is wrong")

    if not favourites_manager.add_service_to_folder(client_id, folder_name, service_id):
        raise HTTPException(
            status_code=400, detail="Error adding service to folder")
    return {"status": "ok"}


@app.delete("/folders/removeservice/{client_id}/{folder_name}/{service_id}")
def remove_service_from_folder(client_id: str, folder_name: str, service_id: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to remove a service from a folder is not a client, something is wrong")

    if not favourites_manager.remove_service_from_folder(client_id, folder_name, service_id):
        raise HTTPException(
            status_code=400, detail="Error removing service from folder")
    return {"status": "ok"}


@app.get("/folders/{client_id}/{folder_name}")
def get_folder(client_id: str, folder_name: str):
    client = accounts_manager.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")
    if client["is_provider"]:
        raise HTTPException(
            status_code=400, detail="The user to get a folder is not a client, something is wrong")

    services = favourites_manager.get_folder_services(client_id, folder_name)
    if services is None:
        raise HTTPException(
            status_code=404, detail="Client does not have that folder")
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
        raise HTTPException(
            status_code=400, detail="The user is not a client, something is wrong")
    if not client_location:
        raise HTTPException(
            status_code=400, detail="Client location is required")
    client_location = validate_location(
        client_location, REQUIRED_LOCATION_FIELDS)

    if not favourites_manager.folder_exists(client_id, folder_name):
        raise HTTPException(
            status_code=404, detail="Client does not have that folder")

    available_services = services_lib.get_available_services(client_location)
    if not available_services:
        raise HTTPException(
            status_code=404, detail="No available services in the area")

    relations_dict = favourites_manager.get_relations(available_services)
    if relations_dict is None:
        raise HTTPException(
            status_code=404, detail="No available services to recommend")

    relations = [(folder, saved_service) for folder, saved_services in relations_dict.items()
                 for saved_service in saved_services]
    interest_predictor = InterestPredictor(relations, folder_name)
    recommendations = interest_predictor.get_interest_prediction()
    return {"status": "ok", "recommendations": recommendations}


@app.post("/certificates/new/{provider_id}")
def add_new_certificate(
    provider_id: str,
    name: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...)
):
    required = {"name", "description", "file"}
    data = {"name": name, "description": description, "file": file}

    user = accounts_manager.get(provider_id)
    if not user:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not user["is_provider"]:
        raise HTTPException(status_code=400, detail="User is not a provider")

    file_contents = file.file.read()
    file_path = save_file(provider_id, file_contents)

    if not file_path:
        raise HTTPException(status_code=400, detail="Error saving file")

    if not certificates_manager.add_certificate(provider_id, name, description, file_path):
        raise HTTPException(status_code=400, detail="Error adding certificate")

    return {"status": "ok"}


@app.delete("/certificates/delete/{provider_id}")
def delete_provider_certificates(provider_id: str):
    user = accounts_manager.get(provider_id)
    if not user:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not user["is_provider"]:
        raise HTTPException(status_code=400, detail="User is not a provider")
    if not certificates_manager.delete_provider_certificates(provider_id):
        raise HTTPException(
            status_code=400, detail="Error deleting certificates")
    return {"status": "ok"}


@app.put("/certificates/update/{provider_id}/{certificate_id}")
def update_certificate(provider_id: str, certificate_id: str, body: dict):
    update = {key: value for key, value in body.items(
    ) if key in VALID_UPDATE_CERTIFICATE_FIELDS}
    if not any(update):
        raise HTTPException(status_code=400, detail="No fields to update")
    extra_fields = set(body.keys()) - VALID_UPDATE_CERTIFICATE_FIELDS
    if extra_fields:
        raise HTTPException(status_code=400, detail=f"""Extra fields: {
                            ', '.join(extra_fields)}""")
    user = accounts_manager.get(provider_id)
    if not user:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not user["is_provider"]:
        raise HTTPException(status_code=400, detail="User is not a provider")
    certificate = certificates_manager.get_certificate_info(
        provider_id, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    new_info = {key: value for key, value in certificate.items()
                if key not in update}
    if not certificates_manager.update_certificate(provider_id, certificate_id, new_info["name"], new_info["description"], new_info["path"], new_info["is_validated"], new_info["expiration_date"]):
        raise HTTPException(
            status_code=400, detail="Error updating certificate")
    send_notification(mobile_token_manager, provider_id, "Certificate updated",
                      f"Your certificate {certificate_id} has been updated")
    return {"status": "ok"}


@app.get("/certificates/all/{provider_id}")
def get_provider_certificates(provider_id: str):
    user = accounts_manager.get(provider_id)
    if not user:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not user["is_provider"]:
        raise HTTPException(status_code=400, detail="User is not a provider")
    certificates = certificates_manager.get_provider_certificates(provider_id)
    return {"status": "ok", "certificates": certificates}


@app.get("/certificates/file/{provider_id}/{certificate_id}")
def get_certificate(provider_id: str, certificate_id: str):
    user = accounts_manager.get(provider_id)
    if not user:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not user["is_provider"]:
        raise HTTPException(status_code=400, detail="User is not a provider")
    certificate = certificates_manager.get_certificate_info(
        provider_id, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    return FileResponse(certificate['path'], media_type="application/pdf")


@app.delete("/certificates/delete/{provider_id}/{certificate_id}")
def delete_certificate(provider_id: str, certificate_id: str):
    user = accounts_manager.get(provider_id)
    if not user:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not user["is_provider"]:
        raise HTTPException(status_code=400, detail="User is not a provider")
    certificate = certificates_manager.get_certificate_info(
        provider_id, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if not certificates_manager.delete_certificate(provider_id, certificate_id):
        raise HTTPException(
            status_code=400, detail="Error deleting certificate")
    if not services_lib.delete_certification(provider_id, certificate_id):
        raise HTTPException(
            status_code=400, detail="Error deleting certification from services")
    return {"status": "ok"}


@app.get("/certificates/unverified")
def get_unverified_certificates(limit: int, offset: int):
    certificates = certificates_manager.get_unverified_certificates(
        limit, offset)
    if not certificates:
        raise HTTPException(
            status_code=404, detail="No unverified certificates")
    return {"status": "ok", "certificates": certificates}
