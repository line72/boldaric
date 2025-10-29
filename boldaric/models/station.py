from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, PickleType
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)

    # Station options
    replay_song_cooldown = Column(Integer, default=0)
    replay_artist_downrank = Column(Float, default=0.995)
    ignore_live = Column(Boolean, default=False)
    current_embedding = Column(PickleType)

    # Relationships
    user = relationship("User", back_populates="stations")
    track_history = relationship("TrackHistory", back_populates="station")
    embedding_history = relationship("EmbeddingHistory", back_populates="station")
