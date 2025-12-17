from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, PickleType, Enum
from sqlalchemy.orm import relationship

from . import Base


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)

    # Station options
    replay_song_cooldown = Column(Integer, default=0)
    replay_artist_downrank = Column(Float, default=0.995)
    ignore_live = Column(Boolean, default=False)
    category = Column(Enum('normalized', 'mood', 'genre', 'old', name='station_category'), 
                      nullable=False, default='normalized')
    current_embedding = Column(PickleType)

    # Relationships
    user = relationship("User", back_populates="stations")
    track_history = relationship("TrackHistory", back_populates="station")
