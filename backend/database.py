from sqlalchemy import create_engine, Column, String, Integer, Float, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import json

DATABASE_URL = "sqlite:///./torrents.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Torrent(Base):
    __tablename__ = "torrents"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String, index=True)
    hash = Column(String, unique=True)
    bytes = Column(Integer)
    host = Column(String)
    split = Column(Integer)
    progress = Column(Integer)
    status = Column(String)
    added = Column(String)
    ended = Column(String, nullable=True)
    rclone_available = Column(Boolean, default=False)
    rclone_available_timestamp = Column(String, nullable=True)
    
    # Storing links as a JSON string
    _links = Column("links", Text)

    @property
    def links(self):
        return json.loads(self._links) if self._links else []

    @links.setter
    def links(self, value):
        self._links = json.dumps(value)


def create_db_and_tables():
    Base.metadata.create_all(bind=engine)
