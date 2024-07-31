import psycopg2
import os
from typing import Optional, Union
from dotenv import load_dotenv


def get_connection() -> Union[psycopg2.extensions.connection, None]:
    try:
        connection = psycopg2.connect(
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.environ["POSTGRES_HOST"],
            port=os.environ["POSTGRES_PORT"],
            database=os.environ["POSTGRES_DB"],
        )

        connection.autocommit = True
        return connection
    except psycopg2.OperationalError:
        return None


def createTable():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            password VARCHAR(50) NOT NULL
        )
        """
    )
    cursor.close()
    connection.close()


def main():
    load_dotenv()
    connection = get_connection()
    if connection:
        print("Connection established")
        createTable()
    else:
        print("Connection failed")


main()
