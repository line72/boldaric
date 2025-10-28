from dataclasses import dataclass


@dataclass
class StationOptions:
    replay_song_cooldown: int = 0
    replay_artist_downrank: float = 0.995
    ignore_live: bool = False
