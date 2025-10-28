from sqlalchemy.orm import declarative_base

Base = declarative_base()

from .user import User
from .station import Station
from .track_history import TrackHistory
from .embedding_history import EmbeddingHistory
