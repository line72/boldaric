#!/usr/bin/env python3
#
# This is a fake player.
#
# It let's you select a station, then, it will
# tell you the next recommended song, and let you:
# a) 👍, b) 👎, or c) let it play
# then get the next recommended song.
#
# The idea here is to test the algorithm
#
# This assume you are running the server on
#  a host some where (or locally)

import argparse
from urllib.parse import urljoin
import requests

def go(host):
    token = authenticate(host)
    station = select_station(host, token)

    while True:
        (status, song) = next_song(host, token, station)
        if not status:
            print('No more songs?')
            return

        handle_song_resp(host, token, station, song)

def handle_song_resp(host, token, station, song):
    print(f'{song["artist"]} - {song["title"]}')
    print('1. 👍')
    print('2. 👎')
    print('3. Let it Play')

    try:
        r = int(input(''))
        if r == 1:
            do_thumbs_up(host, token, station, song)
        elif r == 2:
            do_thumbs_down(host, token, station, song)
        elif r == 3:
            do_play(host, token, station, song)
        else:
            return handle_song_resp(host, tokne, station, song)
    except ValueError:
        return handle_song_resp(host, token, station, song)

def do_thumbs_up(host, token, station, song):
    url = urljoin(host, f'/api/station/{station["id"]}/{song["song_id"]}/thumbs_up')

    r = requests.post(url, headers={'authorization': f'Bearer {token}'}, json={})
    r.raise_for_status()
    
def do_thumbs_down(host, token, station, song):
    url = urljoin(host, f'/api/station/{station["id"]}/{song["song_id"]}/thumbs_down')

    r = requests.post(url, headers={'authorization': f'Bearer {token}'}, json={})
    r.raise_for_status()

def do_play(host, token, station, song):
    url = urljoin(host, f'/api/station/{station["id"]}/{song["song_id"]}')

    r = requests.put(url, headers={'authorization': f'Bearer {token}'}, json={})
    r.raise_for_status()
    

    
def next_song(host, token, station):
    url = urljoin(host, f'/api/station/{station["id"]}')

    r = requests.get(url, headers={'authorization': f'Bearer {token}'})
    r.raise_for_status()

    songs = r.json()['tracks']
    
    if len(songs) == 0:
        return (False, None)
    
    return (True, songs[0])
        
def authenticate(host):
    username = input('Login: ')
    
    url = urljoin(host, '/api/auth')
    
    r = requests.post(url, json={'login': username})
    r.raise_for_status()
    
    return r.json()['token']

def select_station(host, token):
    url = urljoin(host, '/api/stations')
    
    r = requests.get(url, headers={'authorization': f'Bearer {token}'})
    r.raise_for_status()

    stations = r.json()
    for s in stations:
        print(f"{s['id']} - {s['name']}")

    station_id = int(input("Select Station: "))

    station = next(filter(lambda x: x['id'] == station_id, stations))
    return station

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Fake Player')
    parser.add_argument(
        "--host",
        default="http://localhost:8765",
        dest="host",
        help="Host of the boldaric server to test",
    )
    args = parser.parse_args()

    go(args.host)

