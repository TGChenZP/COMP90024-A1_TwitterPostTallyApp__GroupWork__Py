import pandas as pd
import json
import re
from collections import defaultdict as dd


# BEGINNING OF FUNCTIONS
def get_duplicate_and_non_duplicate_sal_dicts(gcc_sa1):
    """ Get dictionaries to match ambiguous sals """

    # build up the special dictionaries used for matching ambiguous SA1s
    dup_sal_dict = {}
    non_dup_sal_dict = {}
    dup_sal_map_dict = {}

    for sal in gcc_sa1:
        # for a duplicate suburb, there will be brackets indicating the state
        if "(" in sal:
            dic = {}
            suburb = ""
            state = ""
            for word in sal.split():
                # the word included in brackets implys that it is a state name
                if word.startswith("("):
                    # use slicing to extract the state from the bracket
                    state = word[word.find('(')+1:word.find(')')]
                    # remove punctuations (especially period) if there is any
                    state = re.sub(r'[^\w\s]', '', state)
                # not included in () means that it is a suburb name or part of the suburb name
                else:
                    suburb += word
            dic[state] = sal

            # if this suburb already exist in dictionary, we update more state
            if suburb in dup_sal_map_dict.keys():
                dup_sal_map_dict[suburb][state] = sal
            # if this suburb has not exist, we add it into dictionary.
            else:
                dup_sal_map_dict[suburb]=dic
            
            dup_sal_dict[sal] = gcc_sa1[sal]
            
        else:
            non_dup_sal_dict[sal] = gcc_sa1[sal]

    return dup_sal_dict, non_dup_sal_dict, dup_sal_map_dict



# TODO: change twitter_data
def update_stats(tweet):
    
    # get location for each tweet
    tweet_location = tweet['includes']['places'][0]['full_name'].lower() 
    # try to just use the sa1 (e.g. try to use 'central coast' if location is 'central coast, new south wales')
    tweet_sal = tweet_location.split(',')[0] 
    

    # if tweet_sal is a duplicated suburb name which are repeated in differnt states:
    if tweet_sal in dup_sal_dict: 
        # extract the state from "tweet_location" as well
        tweet_state = tweet_location.split(',')[1].strip()
        # use duplicated sal dictionary to find the actuall gcc as stored in sal json
        gcc = dup_sal_dict[dup_sal_map_dict[MAP_TweetState_TO_DupSALDict[tweet_state]]]['gcc'] 

    # if tweet_sal is not a duplicated suburb name:
    else:
        # match gcc if the exact string of tweet_sal is in sal.json
        try:
            gcc = non_dup_sal_dict[tweet_sal]['gcc'] 
        # if not, then just ignore
        except:
            # print ignored instances
            print('flushed out:', tweet_location) 
            return 
        
    # the author id from tweets
    id = tweet['_id']

    # update user_stats and gcc_stats
    if id not in user_stats:
        user_stats[id] = [1, {gcc:1}, 1] # tweet count, tweet count from each gcc, diff gccs
    else:
        user_stats[id][0] += 1 # add 1 to tweet count

    if gcc not in user_stats[id][1]:
        user_stats[id][1][gcc] = 1 # add gcc to tally

        user_stats[id][2] += 1 # add to diff gcc tally
    else:
        user_stats[id][1][gcc] += 1 # add tweet count to gcc tally
    
    if gcc not in gcc_stats:
        gcc_stats[gcc] = 1 # add gcc to tally
    else:
        gcc_stats[gcc] += 1 # add tweeter count to gcc tally

# END OF FUNCTIONS




# read the sal file
with open('./data/sal.json', 'r', encoding = 'utf-8') as f:
    sa1 = json.load(f)

# create a list contains all greater capital cities in Australia 
au_gcc = ['1gsyd', '2gmel', '3gbri', '4gade', '5gper', '6ghob', '7gdar', '8acte', '9othe']

gcc_sa1 = {key:sa1[key] for key in sa1 if sa1[key]['gcc'] in au_gcc}
print(gcc_sa1)

dup_sal_dict, non_dup_sal_dict, dup_sal_map_dict = get_duplicate_and_non_duplicate_sal_dicts(gcc_sa1)

# Dictionary mapping twitter data's state back to Duplicated_sal_dict
MAP_TweetState_TO_DupSALDict = {
    'Tasmania': 'tas',
    'Western Australia': 'wa',
    'New South Wales': 'nsw',
    'Victoria': 'vic',
    'South Australia': 'sa',
    'Queensland': 'qld',
    'Northern Territory': 'nt',
    'Australian Capital Territory': 'act'
}

# A dictionary stores the tweet count, tweet count from each gcc and diff gccs count for each author id. It will have the following format:
# user_stats = {'author_id_1': [tweet_count, {'gcc1': count_in_gcc1, 'gcc2': count_gcc2,...}, diff_gccs_count],
#               'author_id_2': [...],...}
user_stats = dict()

# A dictionary stores the number of tweets made in each Greater Capital cities of Australia.
gcc_stats = dict()

# read the twitter data by readline() to avoid running out of memory
with open('./data/twitter-data-small.json', 'r', encoding = 'utf-8') as f:
    tweet = ''
    # the first line of json file is a opening square bracket "[", we skip this line 
    next(f)
    while True:
        line = f.readline()
        if line:
            # if haven't reached the end of a tweet: 
            # "  },\n" is the ending for all tweets, excluding the last tweet and the last one has a ending of "  }\n"
            if line not in ["  },\n", "  }\n"]:
                tweet += line
            # if reached the end of a tweet, remove the ending ","
            else:
                tweet += line.split(',')[0]
                # load json as a dictionary
                tweet_json = json.loads(tweet)
                # analyse this tweet and update stats 
                update_stats(tweet_json)
                # reset tweet
                tweet = ""
        # new_line is false: end of file
        else:
            break



task1 = list(gcc_stats.items())


task2 = sorted(list(user_stats.items()), key = lambda x:x[1][0], reverse=True)


task3 = sorted(list(user_stats.items()), key = lambda x:x[1][2], reverse=True)


# output for task 1
# TODO: add (Greater Sydney) to each gcc
result_task1 = pd.DataFrame(task1, columns = ['Greater Capital City', 'Numbers of Tweets Made'])
print(result_task1)

# TODO: output for task 2 and 3