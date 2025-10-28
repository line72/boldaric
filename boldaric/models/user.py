from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from . import Base


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    
    # Relationships
    stations = relationship("Station", back_populates="user")
