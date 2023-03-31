import pandas as pd
import json
import re
import time

from collections import defaultdict as dd
from mpi4py import MPI
from collections import Counter

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
def update_stats(tweet_location, author_id):
    
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
            # print('flushed out:', tweet_location) 
            return 
        

    # update user_stats
    if author_id not in user_stats:
        user_stats[author_id] = {gcc:1}
    else:
        if gcc not in user_stats[author_id]:
            user_stats[author_id][gcc] = 1 # add gcc to tally and record 1 tweet
        else:
            user_stats[author_id][gcc] += 1 # add tweet count to gcc tally

    # update gcc_stats
    if gcc not in gcc_stats:
        gcc_stats[gcc] = 1 # add gcc to tally
    else:
        gcc_stats[gcc] += 1 # add tweeter count to gcc tally



def get_number_of_city_locations_and_tweets(obj):
    out = str()
    out += str(obj[3])
    out += ' (#'
    out += str(obj[1])
    out += ' tweets - '

    for i in range(len(au_gcc)):
        if au_gcc[i] in obj[2]:
            
            if i != 0:
                out += ', '

            out += '#'
            out += str(obj[2][au_gcc[i]])
            out += str(au_gcc[i][1:])
    
    out += ')'
    return out

# END OF FUNCTIONS




# read the sal file
with open('./data/sal.json', 'r', encoding = 'utf-8') as f:
    sa1 = json.load(f)

# create a list contains all greater capital cities in Australia 
au_gcc = ['1gsyd', '2gmel', '3gbri', '4gade', '5gper', '6ghob', '7gdar', '8acte', '9othe']


gcc_sa1 = {key:sa1[key] for key in sa1 if sa1[key]['gcc'] in au_gcc}


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

# A dictionary stores the tweet count, tweet count from each gcc for each author id. It will have the following format:
# user_stats = {'author_id_1': {'gcc1': count_in_gcc1, 'gcc2': count_gcc2,...},
#               'author_id_2': {...}}
user_stats = dict()

# A dictionary stores the number of tweets made in each Greater Capital cities of Australia.
gcc_stats = dict()

# get rank and size from MPI for this process
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
# get runtime, delete when using spartan. 
time_start = time.time()

# read the twitter data by readline() to avoid running out of memory
with open('./data/twitter-data-small.json', 'r', encoding = 'utf-8') as f:
    tweet_location = ""
    author_id = ""
    # the first line of json file is a opening square bracket "[", we skip this line 
    next(f)
    tweet_index = 0
    # TODO: 这个读法还是很有问题，等于没有parallel。我会尝试去写一个新的readin方法
    while True:
        line = f.readline()
        # if not end of file
        if line:
            # extract author id
            if "author_id" in line:
                author_id = int(re.findall('[0-9]+', line)[0])
            # extract full name location, lower all characters
            elif "full_name" in line:
                tweet_location = re.findall('"([^"]*)"',line)[1].lower()
            # if reached the end of a tweet:
            # "  },\n" is the ending for all tweets, excluding the last tweet and the last one has a ending of "  }\n"
            elif line in ["  },\n", "  }\n"]:
                # update the index of the tweet
                tweet_index += 1
                # this process will only process tweet with tweet_index%size == rank
                if tweet_index % size == rank:
                    # analyse this tweet and update stats 
                    update_stats(tweet_location, author_id)
                # reset tweet location and author id
                tweet_location = ""
                author_id = ""
        # line is false: end of file
        else:
            break

gcc_stats_list = comm.gather(gcc_stats, root = 0)
user_stats_list = comm.gather(user_stats, root = 0)


# only master combines information gatherred from slaves and output the result.
if rank == 0:
    # a temporary dictionary to combine user_stats from gathered user_stats_list from each processor
    # it has the form of : temp_user_stats = {'author_id_1': {'gcc1': count_in_gcc1, 'gcc2': count_gcc2,...},...}
    temp_user_stats = {}
    for d in user_stats_list:
        for author_id, stat in d.items():
            if author_id not in temp_user_stats:
                temp_user_stats[author_id] = stat
            else:
                temp_user_stats[author_id] = Counter(temp_user_stats[author_id]) + Counter(stat)

    # A dictionary stores the tweet count, tweet count from each gcc and diff gccs count for each author id. It will have the following format:
    # user_stats = {'author_id_1': [tweet_count, {'gcc1': count_in_gcc1, 'gcc2': count_gcc2,...}, diff_gccs_count],
    #               'author_id_2': [...],...}
    user_stats = {}
    # calculate number of tweet made and number of different gccs for each author
    for author_id, stat in temp_user_stats.items():
        # total number of tweet = sum of number of tweet made in each gcc
        numTweet = sum(stat.values())
        # number of distinct gcc = the number of keys in stat
        numGcc = len(stat.keys())
        user_stats[author_id] = [numTweet, stat, numGcc]

    # get output for task 1
    task1 = [(author, stat[0]) for author, stat in user_stats.items()]
    task1.sort(key=lambda x:x[1], reverse = True)
    task1 = task1[:10]
    # get author and numTweet as two separated lists
    author_id = [obj[0] for obj in task1]
    number_of_tweets = [obj[1] for obj in task1]
    rank = [f'#{i}' for i in range(1, 11)]
    result_task1 = pd.DataFrame({'Rank': rank, 'Author Id': author_id, 'Number of Tweets Made': number_of_tweets})
    print(result_task1.to_string(index=False))

    # get output for task 2
    temp_gcc_stats = Counter()
    for result in gcc_stats_list:
        temp_gcc_stats += Counter(result)
    
    # add the full name of gcc
    task2_map = {'1gsyd': 'Greater Sydney', '2gmel': 'Greater Melbourne', '3gbri': 'Greater Brisbane', '4gade': 'Greater Adelaide', 
             '5gper': 'Greater Perth', '6ghob': 'Greater Hobart', '7gdar': 'Greater Darwin', '8acte': 'Greater Canberra', 
             '9othe': 'Great Other Territories'}
    gcc_stats = {}
    for gcc, value in temp_gcc_stats.items():
        full_name = task2_map[gcc]
        new_key = "{gcc_short} ({gcc_full})".format(gcc_short=gcc, gcc_full = full_name)
        gcc_stats[new_key] = temp_gcc_stats[gcc]

    task2 = list(gcc_stats.items())    
    result_task2 = pd.DataFrame(task2, columns = ['Greater Capital City', 'Numbers of Tweets Made'])
    # print the output ignoring index
    print(result_task2.to_string(index=False))



    # get output for task 3
    task3 = [(author, user_stats[author][0], user_stats[author][1], user_stats[author][2]) for author in user_stats]
    # sorted by numberOfUniqueCity, in case of a tie (numUniqueCity same), these should be ranked by numTweet.
    task3.sort(key = lambda x:(x[3],x[1]), reverse = True)
    task3 = task3[:10]

    author_id = [obj[0] for obj in task1]
    number_of_city_locations_and_tweets = [get_number_of_city_locations_and_tweets(obj) for obj in task3]
    result_task3 = pd.DataFrame({'Rank': rank, 'Author Id': author_id, 'Number of Unique City Locations and #Tweets': number_of_city_locations_and_tweets})
    print(result_task3.to_string(index=False))

    # get runtime, TODO: delete when using spartan. 
    print(time.time()-time_start)