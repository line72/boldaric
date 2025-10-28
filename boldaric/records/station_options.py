from dataclasses import dataclass
from sqlalchemy import Column, Integer, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base


@dataclass
class StationOptions:
    replay_song_cooldown: int = 0
    replay_artist_downrank: float = 0.995
    ignore_live: bool = False
