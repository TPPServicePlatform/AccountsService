from lib.utils import get_actual_time, get_engine
from typing import Optional, Union
from sqlalchemy import Integer, MetaData, Table, Column, String, Boolean, Float
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import os
import sys
import logging as logger
from sqlalchemy.orm import Session, sessionmaker

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'lib')))

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

    Special for clients (is_provider = False) (when the user is a provider, the following fields are None):
    - reviewer_score: float -- This is the fairness value that the user has when reviewing a product (from 0 -bad- to 1 -good-) (result of the rev2 algorithm)
    - client_count_score: int -- This is the number of reviews that the user has received from providers
    - client_total_score: int -- This is the total score that the user has received from providers
    """

    def __init__(self, engine=None):
        self.engine = engine or get_engine()
        self.create_table()
        logger.getLogger('sqlalchemy.engine').setLevel(logger.DEBUG)
        self.metadata = MetaData()
        self.metadata.bind = self.engine
        self.Session = sessionmaker(bind=self.engine)

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
                Column('validated', Boolean),
                Column('reviewer_score', Float, default=None),
                Column('client_count_score', Integer, default=None),
                Column('client_total_score', Integer, default=None)
            )
            metadata.create_all(self.engine)
            session.commit()

    def insert(self, username: str, uuid: str, complete_name: str, email: str, profile_picture: Optional[str], is_provider: bool, description: Optional[str], birth_date: str) -> bool:
        with Session(self.engine) as session:
            try:
                query = self.accounts.insert().values(
                    uuid=uuid,
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
            except IntegrityError as e:
                logger.error(f"IntegrityError: {e}")
                session.rollback()
                return False
            except SQLAlchemyError as e:
                logger.error(f"SQLAlchemyError: {e}")
                session.rollback()
                return False
        return True

    def get_by_username(self, username: str) -> Optional[dict]:
        with self.engine.connect() as connection:
            query = self.accounts.select().where(self.accounts.c.username == username)
            result = connection.execute(query)
            row = result.fetchone()
            if row is None:
                return None
            return row._asdict()

    def get_by_email(self, email: str) -> Optional[dict]:
        with self.engine.connect() as connection:
            query = self.accounts.select().where(self.accounts.c.email == email)
            result = connection.execute(query)
            row = result.fetchone()
            if row is None:
                return None
            return row._asdict()

    def get(self, id: str) -> Optional[dict]:
        with self.engine.connect() as connection:
            query = self.accounts.select().where(self.accounts.c.uuid == id)
            result = connection.execute(query)
            row = result.fetchone()
            if row is None:
                return None
            return row._asdict()

    def getemail(self, email: str) -> Optional[dict]:
        with self.engine.connect() as connection:
            query = self.accounts.select().where(self.accounts.c.email == email)
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
                query = self.accounts.update().where(
                    self.accounts.c.username == username).values(data)
                session.execute(query)
                session.commit()
            except SQLAlchemyError as e:
                logger.error(f"SQLAlchemyError: {e}")
                session.rollback()
                return False
        return True

    def clear(self):
        self.metadata.drop_all()
        self.metadata.create_all()
