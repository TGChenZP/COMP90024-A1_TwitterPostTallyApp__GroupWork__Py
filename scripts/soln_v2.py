import pandas as pd
import json
import re
import time
import sys
import os

from collections import defaultdict as dd
from mpi4py import MPI
from collections import Counter


# BEGINNING OF NON-MAIN FUNCTIONS
def get_duplicate_and_non_duplicate_sal_dicts(gcc_sal):
    """ Solving the ambiguous dictionary problem: get dictionaries to match ambiguous sals """

    # build up the special dictionaries used for matching ambiguous SA1s
    dup_sal_dict = {}
    non_dup_sal_dict = {}
    dup_sal_map_dict = {}

    for sal in gcc_sal:
        # for a duplicate suburb, there will be brackets indicating the state
        if "(" in sal:
            dic = {}
            suburb = ""
            state = ""
            # separate state and suburb by "("
            for index, word in enumerate(sal.split("(")):
                # the second returned word is the state
                if index != 0:
                    # use slicing to extract the state from the bracket
                    state = sal[sal.find('(')+1:sal.find(')')]
                    # remove punctuations (especially period) if there is any
                    state = re.sub(r'[^\w\s]', '', state)
                # not included in () means that it is a suburb name or part of the suburb name
                else:
                    suburb += word[:-1]
            dic[state] = sal

            # if this suburb already exist in dictionary, we update more state
            if suburb in dup_sal_map_dict.keys():
                dup_sal_map_dict[suburb][state] = sal
            # if this suburb has not exist, we add it into dictionary.
            else:
                dup_sal_map_dict[suburb]=dic
            
            dup_sal_dict[sal] = gcc_sal[sal]
            
        else:
            non_dup_sal_dict[sal] = gcc_sal[sal]

    return dup_sal_dict, non_dup_sal_dict, dup_sal_map_dict



def update_stats(tweet_location, author_id, dup_sal_dict, non_dup_sal_dict, dup_sal_map_dict, MAP_TweetState_TO_DupSALDict, user_stats, gcc_stats, user_gcc_stats):
    """ Helper function to update stats given a tweet we just read """
    
    # try to just use the sa1 (e.g. try to use 'central coast' if location is 'central coast, new south wales')
    tweet_sal = tweet_location.split(',')[0].split('(')[0].strip()
    
    # if tweet_sal is a duplicated suburb name which are repeated in differnt states:
    if tweet_sal in dup_sal_dict: 
        # extract the state from "tweet_location" as well
        tweet_state = tweet_location.split(',')[1].strip()
        # use duplicated sal dictionary to find the actuall gcc as stored in sal json
        gcc = dup_sal_dict[dup_sal_map_dict[tweet_sal][MAP_TweetState_TO_DupSALDict[tweet_state.lower()]]]['gcc'] 

    # if tweet_sal is not a duplicated suburb name:
    else:
        # match gcc if the exact string of tweet_sal is in sal.json
        try:
            gcc = non_dup_sal_dict[tweet_sal]['gcc'] 
        # if not, then just ignore
        except:
            return 
    
    # update user_stats (do not need to consider gcc)
    if author_id not in user_stats:
        user_stats[author_id] = 1
    else:
        user_stats[author_id] += 1

    # update gcc_stats
    if gcc not in gcc_stats:
        gcc_stats[gcc] = 1 # add gcc to tally
    else:
        gcc_stats[gcc] += 1 # add tweet count to gcc tally

    # update user_gcc_stats
    if author_id not in user_gcc_stats:
        user_gcc_stats[author_id] = {gcc:1}
    else:
        if gcc not in user_gcc_stats[author_id]:
            user_gcc_stats[author_id][gcc] = 1 # add gcc to tally and record 1 tweet
        else:
            user_gcc_stats[author_id][gcc] += 1 # add tweet count to gcc tally
    # due to parallelisation, don't need to count up distinct number of locations that tweets were made in just yet.
    # this should be done on node 0



def get_number_of_city_locations_and_tweets(obj, au_gcc):
    """ Helper to get the correct printed output for task 3 """
    out = str()
    out += str(obj[3])
    out += ' (#'
    out += str(obj[1])
    out += ' tweets - '

    first_gcc_printed = False # for formatting the ','
    for i in range(len(au_gcc)):

        if au_gcc[i] in obj[2]:
            
            if first_gcc_printed:
                out += ', '
            
            first_gcc_printed = True

            out += '#'
            out += str(obj[2][au_gcc[i]])
            out += str(au_gcc[i][1:])
    
    out += ')'
    return out



def get_start_end(filename, approximate_start, approximate_end, rank, size, file_byte_size):
    """ Function to get accurate start and end lines byte index for each core to only read necessary part of file """

    f = open(filename, "r")

    # get accurate start
    if rank == 0: # don't need to do anything for node 0 - just use 0th byte
        accurate_start = 0

    else:

        # jump to approximate start
        f.seek(approximate_start)

        # loop over lines and collect end of line's char pos using tell() if the line is an end of json object
        # purpose: start readfile for each parallelised node at the next end of json object after approximate start
        while True: 
            line = f.readline()
            if line in ["  },\n", "  }\n"]:
                accurate_start = f.tell()
                break


    if rank == size-1: # don't need to do anything for final node - just use final byte
        accurate_end = file_byte_size

    else:
        
        # jump to approximate end
        f.seek(approximate_end)

        # loop over lines and collect end of line's char pos using tell() if the line is an end of json object
        # purpose: end readfile for each parallelised node at the next end of json object after approximate end
        while True:
            line = f.readline()
            if line in ["  },\n", "  }\n"]:
                accurate_end = f.tell()
                break

    f.close()

    return accurate_start, accurate_end

# END OF NON-MAIN FUNCTIONS


def main():

    file_address = sys.argv[1]
    sal_file_address = sys.argv[2]


    ## main
    # read the sal file
    with open(sal_file_address, 'r', encoding = 'utf-8') as f:
        sal = json.load(f)

    # hardcode the list contains all greater capital cities in Australia 
    au_gcc = ['1gsyd', '2gmel', '3gbri', '4gade', '5gper', '6ghob', '7gdar', '8acte', '9oter']

    gcc_sal = {key:sal[key] for key in sal if sal[key]['gcc'] in au_gcc}

    # get the duplicate and non duplicated list and mapping dictionaries using the sa1 json readin
    dup_sal_dict, non_dup_sal_dict, dup_sal_map_dict = get_duplicate_and_non_duplicate_sal_dicts(gcc_sal)

    # Hardcode dictionary mapping twitter data's state back to Duplicated_sal_dict
    MAP_TweetState_TO_DupSALDict = {
        'tasmania': 'tas',
        'western australia': 'wa',
        'new south wales': 'nsw',
        'victoria': 'vic',
        'south australia': 'sa',
        'queensland': 'qld',
        'northern territory': 'nt',
        'australian capital territory': 'act'
    }

    # A dictionary that stores the number of tweets made by each author id
    user_stats = dict()

    # A dictionary that stores the number of tweets made in each Greater Capital cities of Australia.
    gcc_stats = dict()

    # A dictionary that stores the tweet count, tweet count from each gcc for each author id. It will have the following format:
    # user_gcc_stats = {'author_id_1': {'gcc1': count_in_gcc1, 'gcc2': count_gcc2,...},
    #               'author_id_2': {...}}
    user_gcc_stats = dict()

    # As each individual node will read this script from start to end, they need to know which node they are within this cluster
    # get rank and size from MPI for this process
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    # get file's total byte size - and how many bytes each core should process
    file_byte_size = os.path.getsize(file_address)
    approximate_block_size = file_byte_size // size

    # get approximate start and approximate end - because we might not exactly chop up our file on the real boundaries
    # of the json objects
    approximate_start = rank*approximate_block_size
    approximate_end = (rank+1)*approximate_block_size

    # use a function to find the correct byte index which is on the border of json objects
    accurate_start, accurate_end = get_start_end(file_address, approximate_start, approximate_end, rank, size, file_byte_size)


    # read the twitter data by readline() to avoid running out of memory
    with open(file_address, 'r', encoding = 'utf-8') as f:
        tweet_location = ""
        author_id = ""

        # jump to the correct start of the file for this node
        f.seek(accurate_start)

        while True:
            line = f.readline()
            
            # if not end of file
            if line:
                # if reached the end of a tweet:
                # "  },\n" is the ending for all tweets, excluding the last tweet and the last one has a ending of "  }\n"
                if line in ["  },\n", "  }\n"]:

                    # analyse this tweet and update stats 
                    update_stats(tweet_location, author_id, dup_sal_dict, non_dup_sal_dict, dup_sal_map_dict, MAP_TweetState_TO_DupSALDict, user_stats, gcc_stats, user_gcc_stats)
                    
                    # if the byte index has suppassed the accurate end then terminate, otherwise continue to read file.
                    if f.tell() >= accurate_end: 
                        break

                    # reset tweet location and author id
                    tweet_location = ""
                    author_id = ""

                # extract author id
                elif "author_id" in line:
                    author_id = int(re.findall('[0-9]+', line)[0])
                # extract full name location, lower all characters
                elif "full_name" in line:
                    tweet_location = re.findall('"([^"]*)"',line)[1].lower()
            
            # end of file - break
            else:
                break
        


    # if node number is root = 0, then it (also) collects the gcc_stat and user_stat dicts (in the form of list of dicts (which happen to be type of sent variables);
    # else: it sends this dictionary object back to the main
    user_stats_list = comm.gather(user_stats, root = 0)
    gcc_stats_list = comm.gather(gcc_stats, root = 0)
    user_gcc_stats_list = comm.gather(user_gcc_stats, root = 0)

    # only master combines information gatherred from slaves and output the result.
    if rank == 0:
        # use 
        user_stats = Counter()
        for d in user_stats_list:
            user_stats = Counter(d) + user_stats

        # get output for task 1
        task1 = [(author, stat) for author, stat in user_stats.items()]
        task1.sort(key=lambda x:x[1], reverse = True)
        task1 = task1[:10]
        # get author and numTweet as two separated lists
        author_id = [obj[0] for obj in task1]
        number_of_tweets = [obj[1] for obj in task1]
        rank = [f'#{i}' for i in range(1, 11)]
        task1_list_for_df = [(rank[i], author_id[i], number_of_tweets[i]) for i in range(len(rank))]
        result_task1 = pd.DataFrame(task1_list_for_df, columns = ['Rank', 'Author Id', 'Numbers of Tweets Made'])

        ## result_task1 = pd.DataFrame({'Rank': rank, 'Author Id': author_id, 'Number of Tweets Made': number_of_tweets})
        print(result_task1.to_string(index=False), '\n')


        # get output for task 2
        temp_gcc_stats = Counter()
        for result in gcc_stats_list:
            temp_gcc_stats += Counter(result)
        
        # add the full name of gcc
        task2_map = {'1gsyd': 'Greater Sydney', '2gmel': 'Greater Melbourne', '3gbri': 'Greater Brisbane', '4gade': 'Greater Adelaide', 
                '5gper': 'Greater Perth', '6ghob': 'Greater Hobart', '7gdar': 'Greater Darwin', '8acte': 'Greater Canberra', 
                '9oter': 'Great Other Territories'}
        gcc_stats = {}
        for gcc, value in temp_gcc_stats.items():
            full_name = task2_map[gcc]
            new_key = "{gcc_short} ({gcc_full})".format(gcc_short=gcc, gcc_full = full_name)
            gcc_stats[new_key] = temp_gcc_stats[gcc]

        
        task2 = list(gcc_stats.items())   
        task2.sort(key= lambda x:x[1], reverse = True) 
        result_task2 = pd.DataFrame(task2, columns = ['Greater Capital City', 'Numbers of Tweets Made'])
        # print the output ignoring index
        print(result_task2.to_string(index=False), '\n')


        # use a temporary dictionary to combine user_gcc_stats from gathered user_gcc_stats_list from each processor
        # it has the form of : temp_user_gcc_stats = {'author_id_1': {'gcc1': count_in_gcc1, 'gcc2': count_gcc2,...},...}
        temp_user_gcc_stats = {}
        for d in user_gcc_stats_list: # for each processor's outcome
            for author_id, stat in d.items():
                if author_id not in temp_user_gcc_stats:
                    temp_user_gcc_stats[author_id] = stat
                else:
                    temp_user_gcc_stats[author_id] = Counter(temp_user_gcc_stats[author_id]) + Counter(stat)

        # A dictionary stores the tweet count, tweet count from each gcc and diff gccs count for each author id. It will have the following format:
        # user_gcc_stats = {'author_id_1': [tweet_count, {'gcc1': count_in_gcc1, 'gcc2': count_gcc2,...}, diff_gccs_count],
        #               'author_id_2': [...],...}
        user_gcc_stats = {}
        # process temp_user_gcc_stats to also derive number of tweet tweeted and number of different gccs tweeted from for each author
        for author_id, stat in temp_user_gcc_stats.items():
            # total number of tweet = sum of number of tweet made in each gcc
            numTweet = sum(stat.values())
            # number of distinct gcc = the number of keys in stat
            numGcc = len(stat.keys())
            user_gcc_stats[author_id] = [numTweet, stat, numGcc]

        # get output for task 3
        task3 = [(author, user_gcc_stats[author][0], user_gcc_stats[author][1], user_gcc_stats[author][2]) for author in user_gcc_stats]
        # sorted by numberOfUniqueCity, in case of a tie (numUniqueCity same), these should be ranked by numTweet.
        task3.sort(key = lambda x:(x[3],x[1]), reverse = True)
        task3 = task3[:10]

        author_id = [obj[0] for obj in task1]
        number_of_city_locations_and_tweets = [get_number_of_city_locations_and_tweets(obj, au_gcc) for obj in task3]
        task3_list_for_df = [(rank[i], author_id[i], number_of_city_locations_and_tweets[i]) for i in range(len(rank))]
        result_task3 = pd.DataFrame(task3_list_for_df, columns = ['Rank', 'Author Id', 'Number of Unique City Locations and #Tweets'])
        # result_task3 = pd.DataFrame({'Rank': rank, 'Author Id': author_id, 'Number of Unique City Locations and #Tweets': number_of_city_locations_and_tweets})
        print(result_task3.to_string(index=False), '\n')


if __name__ == "__main__":
    main()