from dataclasses import dataclass

@dataclass
class Track:
    tid: int = 0
    artist: str = ''
    album: str = ''
    track: str = ''
    track_number: int = 0
    genre: str = ''
    subsonic_id: str = ''
    musicbrainz_artistid: str = ''
    musicbrainz_albumid: str = ''
    musicbrainz_trackid: str = ''
    releasetype: str = ''
    genre_embedding = None
    mfcc_embedding = None
    danceability: float = 0.0
    tempo_stability: float = 0.0
    aggressiveness: float = 0.0
    happiness: float = 0.0
    partiness: float = 0.0
    relaxedness: float = 0.0
    sadness: float = 0.0
    created_at: datetime = None
    updated_at: datetime = None
