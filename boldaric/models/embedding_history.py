from sqlalchemy import Column, Integer, DateTime, ForeignKey, PickleType
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class EmbeddingHistory(Base):
    __tablename__ = "embedding_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    track_history_id = Column(Integer, ForeignKey("track_history.id"), nullable=False)
    embedding = Column(PickleType, nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    station = relationship("Station", back_populates="embedding_history")
