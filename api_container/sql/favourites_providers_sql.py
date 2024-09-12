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


class ProviderFavouriteFolder:
    """
    Account class that stores data in a db through sqlalchemy
    Fields:
    - id: str (unique) ids from folders
    - uid: str (unique) providerid 
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
                Column('folderid', String, primary_key=True, unique=True),
                Column('uid', String, unique=True),
            )
            metadata.create_all(self.engine)
            session.commit()

    def insert(self, folder_id: str, userid: str):
        with Session(self.engine) as session:
            try:
                session.execute(self.accounts.insert().values(
                    folderid=folder_id,
                    uid=userid
                ))
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                return False
            except SQLAlchemyError as e:
                logger.error(e)
                return False

    def get(self, folder_id: str):
        with Session(self.engine) as session:
            result = session.execute(self.accounts.select().where(
                self.accounts.c.folderid == folder_id)).fetchone()
            if result is None:
                return None
            return dict(result)

    def clear(self):
        self.metadata.drop_all()
        self.metadata.create_all()
