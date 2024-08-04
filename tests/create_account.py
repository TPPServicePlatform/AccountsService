import requests
import json


def create_account():
    url = "http://localhost:9212/api/accounts"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "username": "marco",
        "password": "polo",
        "complete_name": "Marco Polo",
        "email": "marco@polo.com",
        "profile_picture": "https://cdn.britannica.com/53/194553-050-88A5AC72/Marco-Polo-Italian-portrait-woodcut.jpg",
        "is_provider": True
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 201:
        print("Account created successfully:", response.json())
    else:
        print("Failed to create account:", response.status_code, response.text)


if __name__ == "__main__":
    create_account()
