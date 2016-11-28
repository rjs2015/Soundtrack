from flask import Flask, jsonify, request, render_template

import numpy as np
import pandas as pd
import pickle
from sqlalchemy import create_engine
engine = create_engine('postgresql://rsingh:rsingh@localhost:5432/playlist')

#---------- MODEL AND SAMPLE DF IN MEMORY ----------------#

# Load in pickled models
with open('playlist_models','r') as f: 
    model_matrix = pickle.load(f)

# Load in pickled sample feature dataframe    
    
with open('ft','r') as f: 
    sample_features = pickle.load(f)

# Initialize playlist variables
    
playlist = []   
categories = ['Party','Chill','Sleep','Workout','Travel']
old_category = ''
breakdown_dict = {'Chill': 0, 'Party': 0, 'Sleep': 0, 'Travel': 0, 'Workout': 0}
artist_info = []

#---------- URLS AND WEB PAGES -------------#

# Initialize the app
app = Flask(__name__)

# Homepage
@app.route("/")
def index():

    return render_template("index.html")

@app.route("/main/", methods=["POST"])
def score():

    ''' Compile playlist with songs from artists, ranked by category alignment '''

    data = request.json

    global playlist, breakdown_dict, old_category, artist_info

    length = data["info"][0]    
    new_category = data["info"][1]
    artist = data["info"][2]

    if artist=='clear':
        
# If user cleared playlist, reset variables to initial values        

        playlist = pd.DataFrame()
        breakdown_dict = {'Chill': 0, 'Party': 0, 'Sleep': 0, 'Travel': 0, 'Workout': 0,'playlist_info': 'No songs - add some artists!'}
        artist_info = []

    else:
        
# Otherwise, if a new artist is added, fetch that artist's tracks from psql database, and use predicted 
# probabilities for tracks of belonging to each category to measure song alignment to each one
        
        try:
            previous_artists = playlist.index.levels[3]
        except:
            previous_artists = []

        if artist not in previous_artists:
            
            artist_info.append(artist)

            query = pd.read_sql_query("""SELECT * from spotify_song_data ssd 
                                     INNER JOIN gracenote_song_data gsd ON ssd.id=gsd.id 
                                     INNER JOIN artist_songs asongs ON ssd.id = asongs.id 
                                     WHERE asongs.artist_name='"""+artist+"""'""",con=engine)

# Exclude some columns from the query, create dummies from Gracenote variables, and format data in the
# to have the same variables/order of the sample feature dataframe

            query = query.ix[:,[1,31,2,33,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,22,23,24,25,26,27,28]]

            query.genre_1 = query.genre_1.fillna('no_genre')
            query.genre_2 = query.genre_2.fillna('no_genre_2')
            query.mood_1 = query.mood_1.fillna('no_mood')
            query.artist_type_1 = query.artist_type_1.fillna('no_artist')
            query = pd.concat([query, pd.get_dummies(query.genre_1,prefix='genre_1'),
                                      pd.get_dummies(query.genre_2,prefix='genre_2'),
                                      pd.get_dummies(query.mood_1,prefix='mood_1'),
                                      pd.get_dummies(query.artist_type_1,prefix='artist_1')],axis=1)

            query = query.drop(['genre_1','artist_type_1','genre_2','mood_1'],axis=1)
            query = query.groupby('id',as_index=False).first()
            query = query.set_index(['id','name','artist','artist_name']).drop(['popularity','cutoff'],axis=1)

            for var in sample_features.columns:
                if var not in query.columns:
                    query[var] = 0

            query = query[list(sample_features.columns)]

# Create (if currently empty) or extend a playlist based on the user specified artists. For each song,
# predict alignment to each category using predict_proba from the pickled models.  When a user chooses a 
# category, we will sort on this metric to return songs most aligned to that category for their playlist
            
            if len(playlist)==0:
                    
                playlist = pd.DataFrame(index=query.index)

                for cat in categories:
                    playlist[cat] = pd.Series(model_matrix[cat].predict_proba(query)[:,1],
                            index=query.index,name=cat)

            else:

                playlist_extension =  pd.DataFrame(index=query.index)

                for cat in categories:
                    playlist_extension[cat] = pd.Series(model_matrix[cat].predict_proba(query)[:,1],
                            index=query.index,name=cat)

                playlist = pd.concat([playlist,playlist_extension])

# Resort tracks only if the category changes or a new artist is added (to avoid unnecessary sorting
# when the slider is moved).  Calculate the playlist's total category alignment scores to 
# create the visualization blob, captured in 'playlist_breakdown'.
        
        if (new_category!=old_category) or (artist not in previous_artists):
            playlist.sort_values(new_category,ascending=False,inplace=True)
            old_category = new_category  
        
        playlist_breakdown = playlist[:min(length,len(playlist))].sum()
        playlist_breakdown = playlist_breakdown/playlist_breakdown.max()

        breakdown_dict = {}
        for cat in categories:
            breakdown_dict[cat] = round(playlist_breakdown[cat],2)

# Create preformatted text blobs containing artists and contents of playlist, for display
# in the application
            
        playlist_songs = playlist.index.get_level_values('name')
        playlist_info = []
        line = []
        for i in range(length):
            line.append(str(min(i+1,len(playlist_songs))) + ". " + playlist_songs[i])
            if len('   '.join(line)) > 40:
                line = '   '.join(line) + "\n"
                playlist_info.extend(line)
                line=[]
            elif i==length-1:
                line = '   '.join(line)
                playlist_info.extend(line)
        playlist_info = ''.join(playlist_info)
    
        playlist_artists = []
        line = []
        for artist in artist_info:
            line.append(artist)
            if len('   '.join(line + [''])) > 50:
                line = '   '.join(line) + "\n\n"
                playlist_artists.extend(line)
                line=[]
            elif artist==artist_info[-1]:
                line = '   '.join(line)
                playlist_artists.extend(line)
        playlist_artists = ''.join(playlist_artists)

        breakdown_dict['playlist_info'] = playlist_info
        breakdown_dict['artist_info'] = playlist_artists
        
    return jsonify(breakdown_dict)

#--------- RUN WEB APP SERVER ------------#

# Start the app server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)