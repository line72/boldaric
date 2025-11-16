from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class TrackHistory(Base):
    __tablename__ = "track_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    is_thumbs_downed = Column(Boolean, default=False)
    rating = Column(Integer, default=0)  # Add rating column
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Add foreign key relationship to Track
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)

    # Relationships
    station = relationship("Station", back_populates="track_history")
    track = relationship("Track", back_populates="history_entries")
