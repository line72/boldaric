#!/usr/bin/env python
#
# Run through some tests of songs and checks similarities with
#  different algorithms

import os
import argparse

import boldaric
from boldaric.models.track import Track

# ((artist1, album1, song1), (artist2, album2, song2), MOOD_CHECK, GENRE_CHECK)
checks = [
    (
        ('Blind Guardian', 'Imaginations From the Other Side', 'Imaginations From the Other Side'),
        ('Blind Guardian', 'Nightfall in Middle-Earth', 'The Curse of Feanor'),
        True, True
    ),
    (
        ('Blind Guardian', 'Imaginations From the Other Side', 'Imaginations From the Other Side'),
        ('Pharaoh', 'Be Gone', 'Be Gone'),
        False, True
    ),
    (
        ('Pensées Nocturnes', 'Douce Fange', 'Quel sale bourreau'),
        ("The Beatles", "The Beatles", "Why Don't We Do It in the Road?"),
        False, False
    ),
    (
        ("Paysage d'Hiver","Im Wald","Über den Bäumen"),
        ("Darkthrone","Transilvanian Hunger","Slottet i det fjerne"),
        False, True
    ),
]

def check_score(outcome, score, needed_score):
    if outcome and score >= needed_score:
        return '✅'
    elif not outcome and score < needed_score:
        return '✅'
    else:
        return '❌'

def main(db):
    with db.Session() as session:
        for a1, a2, mood, genre in checks:
            song1 = session.query(Track).filter(Track.artist == a1[0],
                                                Track.album == a1[1],
                                                Track.title == a1[2]).first()
            song2 = session.query(Track).filter(Track.artist == a2[0],
                                                Track.album == a2[1],
                                                Track.title == a2[2]).first()

            results1 = boldaric.utils.compute_cosine_similarity_explanation(
                boldaric.feature_helper.track_to_embeddings_mood(song1),
                boldaric.feature_helper.track_to_embeddings_mood(song2)
            )
            results2 = boldaric.utils.compute_cosine_similarity_explanation(
                boldaric.feature_helper.track_to_embeddings_genre(song1),
                boldaric.feature_helper.track_to_embeddings_genre(song2)
            )

            NEEDED_SCORE=0.75
            
            mood_results = check_score(mood, results1['similarity_score'], NEEDED_SCORE)
            genre_results = check_score(genre, results2['similarity_score'], NEEDED_SCORE)

            print(f'{song1.artist} - {song1.title} vs {song2.artist} - {song2.title}: {mood_results}|{genre_results}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Similarity Analyzer")
    parser.add_argument(
        "-d",
        "--db-path",
        default="./db",
        dest="db_path",
        help="Path to the station database",
    )
    args = parser.parse_args()

    db_name = os.path.join(args.db_path, "stations.db")
    stationdb = boldaric.StationDB(db_name)
    
    main(stationdb)
    

