#!/usr/bin/env python
#
# Run through some tests of songs and checks similarities with
#  different algorithms

import os
import argparse

import rich.table
import rich.console

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
    (
        ("Smashing Pumpkins","Siamese Dream","Today"),
        ("Smashing Pumpkins","Siamese Dream","Disarm"),
        True, True
    ),
    (
        ("The Smashing Pumpkins","Mellon Collie and the Infinite Sadness","Bullet With Butterfly Wings"),
        ("Smashing Pumpkins","Siamese Dream","Today"),
        True, True
    ),
    (
        ("Nirvana","In Utero","All Apologies"),
        ("Smashing Pumpkins","Siamese Dream","Today"),
        True, True
    )
]

def check_score(outcome, score, needed_score):
    if outcome and score >= needed_score:
        return '✅'
    elif not outcome and score < needed_score:
        return '✅'
    else:
        return '❌'

def main(db, score):
    table = rich.table.Table()
    table.add_column('Song 1')
    table.add_column('Song 2')
    table.add_column('Similar Mood?')
    table.add_column('Pass?')
    table.add_column('Score', max_width=7)
    table.add_column('Similar Genre?')
    table.add_column('Pass?')
    table.add_column('Score', max_width=7)
    
    with db.Session() as session:
        for a1, a2, mood, genre in checks:
            song1 = session.query(Track).filter(Track.artist == a1[0],
                                                Track.album == a1[1],
                                                Track.title == a1[2]).first()
            song2 = session.query(Track).filter(Track.artist == a2[0],
                                                Track.album == a2[1],
                                                Track.title == a2[2]).first()

            results1 = boldaric.utils.compute_cosine_similarity_explanation(
                boldaric.feature_helper.MoodFeatureHelper.track_to_embeddings(song1),
                boldaric.feature_helper.MoodFeatureHelper.track_to_embeddings(song2)
            )
            results2 = boldaric.utils.compute_cosine_similarity_explanation(
                boldaric.feature_helper.GenreFeatureHelper.track_to_embeddings(song1),
                boldaric.feature_helper.GenreFeatureHelper.track_to_embeddings(song2)
            )

            NEEDED_SCORE=score
            
            mood_results = check_score(mood, results1['similarity_score'], NEEDED_SCORE)
            genre_results = check_score(genre, results2['similarity_score'], NEEDED_SCORE)

            table.add_row(
                f'{song1.artist} - {song1.title}',
                f'{song2.artist} - {song2.title}',
                str(mood), mood_results, str(results1["similarity_score"]),
                str(genre), genre_results, str(results2["similarity_score"])
            )
            #print(f'{song1.artist} - {song1.title} vs {song2.artist} - {song2.title}: {mood_results}|{genre_results}')

    console = rich.console.Console()
    console.print(table)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Similarity Analyzer")
    parser.add_argument(
        "-d",
        "--db-path",
        default="./db",
        dest="db_path",
        help="Path to the station database",
    )
    parser.add_argument(
        "-s",
        "--score",
        type=float,
        default=0.9,
        help="Minimum score to be considered similar"
    )
    args = parser.parse_args()

    db_name = os.path.join(args.db_path, "stations.db")
    stationdb = boldaric.StationDB(db_name)
    
    main(stationdb, args.score)
    

