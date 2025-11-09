from sqlalchemy import Column, Integer, String
from . import Base

class Genre(Base):
    __tablename__ = "genres"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, unique=True, nullable=False)
