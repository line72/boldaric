from dataclasses import dataclass
from enum import Enum


class StationCategory(Enum):
    DEFAULT = "default"
    MOOD = "mood"
    GENRE = "genre"
    OLD = "old"


@dataclass
class StationOptions:
    replay_song_cooldown: int = 0
    replay_artist_downrank: float = 0.995
    ignore_live: bool = False
    category: StationCategory = StationCategory.DEFAULT
