from sqlalchemy import Column, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship
from . import Base

class TrackGenre(Base):
    __tablename__ = "tracks_genres"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    genre_id = Column(Integer, ForeignKey("genres.id"), nullable=False)
    score = Column(Float)
    
    # Relationships
    track = relationship("Track", back_populates="track_genres")
    genre = relationship("Genre")
