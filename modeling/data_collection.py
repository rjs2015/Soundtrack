import numpy as np
import pandas as pd
import spotipy
import spotipy.util as util

token = util.prompt_for_user_token('',
                                   client_id='', 
                                   client_secret='',
                                   redirect_uri='')
spotify = spotipy.Spotify(auth=token)

category_map = {1:'Party',2:'Workout',3:'Chill',4:'Sleep',5:'Travel'}

# Collect tracks and their information based on Spotify's Category/Playlist structure

def get_category_playlists():
    ''' Get Spotify Categories and associated playlists '''
    categories = {category['name']:category['id'] for category in 
                  spotify.categories(country='US',limit=40)['categories']['items']}
    playlists = {}
    for cat_name,cat_id in categories.iteritems():
        try:
            for playlist in spotify.category_playlists(cat_id,limit=50)['playlists']['items']:
                playlists[cat_name,playlist['name']] = playlist['id'] 
        except:
            pass
    
    return playlists

def get_playlist_tracks(playlists, category_map):       
    ''' Get tracks for Spotify playlists '''    
    playlist_tracks = {}
    playlist_sub = {cat_playlist:playlist_id for cat_playlist,playlist_id
                    in playlists.iteritems() if cat_playlist[0] in category_map.values()}

    for cat_playlist,playlist_id in playlist_sub.iteritems():
        try:
            tracks = spotify.user_playlist_tracks('spotify',playlist_id,limit=100)['items']
            playlist_tracks[cat_playlist] = [[i['track']['name'], i['track']['id']] for i in tracks]
        except:
            pass
        
    return playlist_tracks        
    
def get_audio_feature_df(playlist_tracks):  
    ''' Get Spotify audio features for tracks '''       
    features = []

    for cat_playlist,tracks in playlist_tracks.iteritems():
        track_ids = [i[1] for i in tracks if i[1]!=None]
        category = cat_playlist[0]
        features_add = spotify.audio_features(tracks=track_ids)
        for i in features_add:
            try:
                i['category'] = category
            except:
                del i
        features.extend(features_add)

    features = [i for i in features if i is not None]

    feature_df = pd.DataFrame(features).drop(['analysis_url','track_href','type','uri'],axis=1)
    
    return feature_df

def chunks(l, n):
    n = max(1, n)
    return [l[i:i+n] for i in range(0, len(l), n)]

def get_other_track_info_df(feature_df):
    ''' Get general track information from Spotify '''       
    spotify_title_artists = []

    for track_chunk in chunks(feature_df.id.unique(),50):
        for track in spotify.tracks(track_chunk)['tracks']:
            title_artist = {}
            artists = [[artist['id'],artist['name'].encode('ascii', 'ignore')] for artist in track['artists']]
            name = track['name'].encode('ascii', 'ignore')
            ID = track['id']
            title_artist['id'] = ID
            title_artist['title'] = name
            title_artist['artist'] = artists
            title_artist['explicit'] = track['explicit']
            spotify_title_artists.append(title_artist)

    return pd.DataFrame(spotify_title_artists)

playlists = get_category_playlists()
playlist_tracks = get_playlist_tracks(playlists, category_map)
feature_df = get_audio_feature_df(playlist_tracks)
other_track_info_df = get_other_track_info_df(feature_df)