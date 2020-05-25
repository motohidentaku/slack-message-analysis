from contextlib import contextmanager
import json
import os
from typing import Optional

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column, Boolean, String, Float, JSON, create_engine, PrimaryKeyConstraint)
from sqlalchemy.orm import Session, sessionmaker

Base = declarative_base()
_session: Optional[Session] = None


class User(Base):
    __tablename__ = 'users'
    id = Column(String)
    name = Column(String, nullable=False)
    email = Column(String)
    raw = Column(JSON, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint('id', sqlite_on_conflict='REPLACE'),
    )


class Channel(Base):
    __tablename__ = 'channels'
    id = Column(String)
    name = Column(String, nullable=False)
    is_member = Column(Boolean, nullable=False)
    raw = Column(JSON, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint('id', sqlite_on_conflict='REPLACE'),
    )


class Message(Base):
    __tablename__ = 'messages'
    timestamp = Column(Float)
    channel_id = Column(String)
    user_id = Column(String)
    subtype = Column(String)
    raw = Column(JSON)
    __table_args__ = (
        PrimaryKeyConstraint('timestamp', 'channel_id', 'user_id', 'subtype',
                             sqlite_on_conflict='REPLACE'),
    )


def init_db(path: str) -> None:
    global _session
    if _session is not None:
        return
    engine = create_engine(
        'sqlite:///{}'.format(os.path.abspath(path)),
        json_serializer=lambda o: json.dumps(
            o, ensure_ascii=False, separators=(',', ':')))
    Base.metadata.create_all(engine)
    _session = sessionmaker(bind=engine)  # type: ignore


@contextmanager
def transaction():
    assert _session
    s = _session()
    try:
        yield s
        s.commit()
    except Exception as e:
        s.rollback()
        raise e
