from lib.utils import get_actual_time, get_engine
from typing import Optional, Union
from sqlalchemy import MetaData, Table, Column, String, Boolean
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import os
import sys
import logging as logger
from sqlalchemy.orm import Session, sessionmaker
import uuid

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'lib')))

HOUR = 60 * 60
MINUTE = 60
MILLISECOND = 1_000


class FavouritesFolderUser:
    """
    Account class that stores data in a db through sqlalchemy
    Fields:
    - uuid: str (unique) [pk]
    - id: str (unique) ids from folders
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
                Column('folderid', String, unique=True),
            )
            metadata.create_all(self.engine)
            session.commit()

    def insert(self, userid: str):
        with Session(self.engine) as session:
            try:
                new_uuid = str(uuid.uuid4())
                session.execute(self.accounts.insert().values(
                    uuid=userid,
                    folderid=new_uuid
                ))
                session.commit()
                return new_uuid
            except IntegrityError:
                session.rollback()
                return False
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error inserting into accounts: {e}")
                return False

    def get(self, userid: str):
        with Session(self.engine) as session:
            try:
                result = session.execute(self.accounts.select().where(
                    self.accounts.c.uuid == userid))
                return result.fetchone()
            except SQLAlchemyError as e:
                logger.error(f"Error getting from accounts: {e}")
                return None

    def get_user_folder(self, userid: str, folderid: str):
        with Session(self.engine) as session:
            try:
                result = session.execute(self.accounts.select().where(
                    self.accounts.c.uuid == userid and self.accounts.c.folderid == folderid))
                return result.fetchone()
            except SQLAlchemyError as e:
                logger.error(f"Error getting from accounts: {e}")
                return None

    def get_folder(self, folderid: str):
        with Session(self.engine) as session:
            try:
                result = session.execute(self.accounts.select().where(
                    self.accounts.c.folderid == folderid))
                return result.fetchone()
            except SQLAlchemyError as e:
                logger.error(f"Error getting from accounts: {e}")
                return None

    def clear(self):
        self.metadata.drop_all()
        self.metadata.create_all()
