import time
from typing import Optional, Union
from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from lib.utils import get_actual_time, get_engine
import logging as logger
import traceback
from sqlalchemy.orm import Session

HOUR = 60 * 60
MINUTE = 60
MILLISECOND = 1_000

# TODO: (General) -> Create tests for each method && add the required checks in each method

class Accounts:
    """
    Account class that stores data in a db through sqlalchemy
    Fields:
    - uuid: str (unique) [pk]
    - username: str (unique)
    - complete_name: str
    - email: str (unique)
    - profile_picture: str
    - is_provider: boolean
    - created_at: datetime
    - description: str
    - birth_date: datetime
    - validated: boolean
    """

    def __init__(self):
        self.engine = get_engine()
        self.create_table()
        logger.getLogger('sqlalchemy.engine').setLevel(logger.DEBUG)

    def create_table(self):
        with Session(self.engine) as session:
            metadata = MetaData()
            self.accounts = Table(
                'accounts',
                metadata,
                Column('uuid', String, primary_key=True, unique=True),
                Column('username', String, unique=True),
                Column('complete_name', String),
                Column('email', String, unique=True),
                Column('profile_picture', String),
                Column('is_provider', Boolean),
                Column('created_at', String),
                Column('description', String),
                Column('birth_date', String),
                Column('validated', Boolean)
            )
            metadata.create_all(self.engine)
            session.commit()

    def insert(self, username: str, uid: str, complete_name: str, email: str, profile_picture: Optional[str], is_provider: bool, description: Optional[str], birth_date: str) -> bool:
        with Session(self.engine) as session:
            try:
                query = self.accounts.insert().values(
                    uid=uid,
                    username=username,
                    complete_name=complete_name,
                    email=email,
                    profile_picture=profile_picture,
                    is_provider=is_provider,
                    description=description,
                    birth_date=birth_date,
                    validated=False,
                    created_at=get_actual_time()
                )
                session.execute(query)
                session.commit()
                return True
            except IntegrityError as e:
                logger.error(f"IntegrityError: {e}")
                session.rollback()
                return False
            except SQLAlchemyError as e:
                logger.error(f"SQLAlchemyError: {e}")
                session.rollback()
                return False

    def get(self, username: str) -> Optional[dict]:
        with self.engine.connect() as connection:
            query = self.accounts.select().where(self.accounts.c.username == username)
            result = connection.execute(query)
            row = result.fetchone()
            if row is None:
                return None
            return row._asdict()

    def delete(self, username: str) -> bool:
        with Session(self.engine) as session:
            try:
                query = self.accounts.delete().where(self.accounts.c.username == username)
                session.execute(query)
                session.commit()
            except SQLAlchemyError as e:
                logger.error(f"SQLAlchemyError: {e}")
                session.rollback()
                return False
            return True
    
    def update(self, username: str, data: dict) -> bool:
        with Session(self.engine) as session:
            try:
                query = self.accounts.update().where(self.accounts.c.username == username).values(data)
                session.execute(query)
                session.commit()
            except SQLAlchemyError as e:
                logger.error(f"SQLAlchemyError: {e}")
                session.rollback()
                return False
            return True
