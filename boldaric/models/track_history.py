from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class TrackHistory(Base):
    __tablename__ = "track_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    subsonic_id = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    title = Column(String, nullable=False)
    album = Column(String, nullable=False)
    is_thumbs_downed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    station = relationship("Station", back_populates="track_history")
