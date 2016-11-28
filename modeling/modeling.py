import numpy as np
import pandas as pd
import pickle
from sklearn.cross_validation import train_test_split
from sklearn import tree, ensemble, cross_validation, metrics

gn_songs = pickle.load(open('master_songs.pkl', 'r'))

category_map = {1:'Party',2:'Workout',3:'Chill',4:'Sleep',5:'Travel'}

# Some tracks appear in multiple categories.  For our purposes, we want a 1:1 mapping,
# so these tracks are reassigned into the one category they most closely fit 
# using a model based on the existing single-category tracks.

def map_tracks_to_one_category(feature_df, other_track_info_df, category_map):
    '''Map tracks in multiple Spotify categories to the category to which they
       are most aligned'''
    
    # Isolate the tracks in one category from those in two

    df = pd.merge(feature_df, other_track_info_df[['id','explicit']],how='left')
    df.category = df.category.map(dict(zip(category_map.values(),category_map.keys())))
    df = df.dropna()

    single_cat_tracks = [k for k,v in dict(df.groupby(['id']).category.unique()).iteritems() if len(v)<2]
    double_cat_tracks = [[k,list(v)] for k,v in dict(df.groupby(['id']).category.unique()).iteritems() if len(v)==2]
    three_plus_cat_tracks = [k for k,v in dict(df.groupby(['id']).category.unique()).iteritems() if len(v)>2]

    df = df[np.logical_not(df.id.isin(three_plus_cat_tracks))].groupby(['id'],as_index=False).mean()

    df_single_cat = df[df.id.isin(single_cat_tracks)]
    
    # For every combination of two categories, create a classifier to assign tracks 
    # that were originally in both to one

    reclassified_duplicates = []
    for i in sorted(category_map.keys())[:-1]:
        for j in sorted(category_map.keys())[i:]:
            X_single_cat = df_single_cat[df_single_cat.category.isin([i,j])].drop(['category','id'],axis=1)
            y_single_cat = df_single_cat[df_single_cat.category.isin([i,j])].category
            GBtree = ensemble.GradientBoostingClassifier(min_samples_leaf=10,
                                                         max_depth=2,
                                                         max_features=4,
                                                         n_estimators=100)
            GBtree.fit(X_single_cat, y_single_cat)

            tracks_in_both_cats = [n[0] for n in double_cat_tracks if (i in n[1]) & (j in n[1])]
            if len(tracks_in_both_cats)>0:
                reclassified_duplicates.extend(zip(df[df.id.isin(tracks_in_both_cats)].id,
                    GBtree.predict(df[df.id.isin(tracks_in_both_cats)].drop(['id','category'],axis=1))))

    # Merge the reassigned categories with the original dataframe, and fill the
    # non-duplicate records with the previous categories

    reclassified = pd.DataFrame(reclassified_duplicates,columns = ['id','final_cat'])
    df = pd.merge(df, reclassified, how='left')
    df.final_cat = df.final_cat.fillna(df.category)
    df.category = df.final_cat
    df = df.drop('final_cat',axis=1)

    return df

def add_gracenote_data(spotify_df, gn_songs):    
    '''Merge Gracenote and Spotify track information to create one modeling dataframe
       Gracenote data comes from pickle file.'''

    df = pd.merge(spotify_df,gn_songs[['id','genre_1']],how='left').fillna('no_genre')
    df = pd.merge(df,gn_songs[['id','genre_2']],how='left').fillna('no_genre_2')
    df = pd.merge(df,gn_songs[['id','mood_1']],how='left').fillna('no_mood')
    df = pd.merge(df,gn_songs[['id','artist_type_1']],how='left').fillna('no_artist')
    
    # Create dummies from Gracenote variables
    
    df = pd.concat([df, pd.get_dummies(df.genre_1,prefix='genre_1'),
                        pd.get_dummies(df.genre_2,prefix='genre_2'),
                        pd.get_dummies(df.mood_1,prefix='mood_1'),
                        pd.get_dummies(df.artist_type_1,prefix='artist_1')],axis=1)

    df = df.drop(['genre_1','artist_type_1','genre_2','mood_1'],axis=1)
    
    return df

def model_category_alignment(modeling_df, category_map, pickle_models=False):
    '''For each category, create and store a model to determine a track's 
       alignment with that category'''

    model_dict = {}

    for category in category_map.keys():
        y = modeling_df.category==category
        X = modeling_df.drop(['category','id'],axis=1)
        X_train, X_test, y_train, y_test = cross_validation.train_test_split(X, y, test_size=.33)

        model = ensemble.GradientBoostingClassifier(max_features=5,
                                                 max_depth=3,
                                                 min_samples_leaf=30,
                                                 min_samples_split=30,
                                                 n_estimators=100)
    
        model.fit(X_train,y_train)
#         print(category_map[category])
#         print(metrics.classification_report(y_test,model.predict(X_test)))
        model_dict[cateagory_map[category]] = model
        
    if pickle_models == True:
        pickle.dump(model_dict, open('playlist_models.p', 'wb'))
    
    return model_dict
    
spotify_df = map_tracks_to_one_category(feature_df, other_track_info_df, category_map)
modeling_df = add_gracenote_data(spotify_df, gn_songs)    
model_dict = model_category_alignment(modeling_df, category_map) 