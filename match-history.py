import requests
import json
import datetime
from collections import defaultdict
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests_toolbelt import sessions

apiKey = "RGAPI-7988f2b9-a4dd-4151-ae5e-9a432ce3cb68"

# set up retry strategy for API calls w/exponential backoff
retry_strategy = Retry(
    total = 5,
    status_forcelist = [429, 500, 502, 503, 504],
    method_whitelist = ["GET"],
    backoff_factor = 1
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = sessions.BaseUrlSession(base_url="https://na1.api.riotgames.com")
http.mount("https://", adapter)

class Match(object):
    gameId = 0
    win = False
    lane = ""
    date = datetime.datetime.now()
    def __init__(self, gameId, timestamp, lane):
        self.gameId = gameId
        self.date = datetime.datetime.fromtimestamp(timestamp / 1000) # Riot's timestamps come down to the millisecond which was blowing up the conversion so we need to divide them
        self.lane = lane

def main():
    accountId = getAccountId("Rement")
    matches = getMatchlist(accountId)
    enrichedMatches = enrichMatches(matches, accountId)
    createDayLookup(enrichedMatches)

def getAccountId(summonerName):
    accountEndpoint = "/lol/summoner/v4/summoners/by-name/"
    params = {'api_key': apiKey}
    r = http.get(accountEndpoint + summonerName, params=params)

    summonerId = r.json().get('accountId')
    print("{}:{}".format(summonerName, summonerId))
    return summonerId

def getMatchlist(accountId):
    accountEndpoint = "/lol/match/v4/matchlists/by-account/"
    params = {'api_key': apiKey}

    matchList = []

    # this is pretty gross but Riot's API doesn't return a proper total number of matches, so you just need to keep calling until there are no matches
    thereAreStillMatches = True
    i = 0
    while thereAreStillMatches:
        params['beginIndex'] = i
        r = http.get(accountEndpoint + accountId, params=params)
        matches = r.json().get('matches')
        for match in matches:
            matchList.append(Match(match['gameId'], match['timestamp'], match['lane']))
        thereAreStillMatches = len(matches) > 0
        i += 100

    print("Retrieved {} matches".format(len(matchList)))
    return matchList

def enrichMatches(matches, accountId):
    matchEndpoint = "/lol/match/v4/matches/"
    params = {'api_key': apiKey}

    for match in matches:
        print("Enriching match {}".format(match.gameId))
        r = http.get(matchEndpoint + str(match.gameId), params=params)
        matchDict = r.json()

        # use a bunch of generators to parse the response JSON. Not sure if this is the most efficient way but seems pretty nice.
        # if anything doesn't exist it will blow up so hopefully Riot doesn't send malformed data

        # get the participant ID of the next participantIdentity where the player account Id matches the provided account ID
        participantId = next(participantIdentities['participantId'] for participantIdentities in matchDict['participantIdentities'] if participantIdentities['player']['accountId'] == accountId)

        # get the team ID of the next participant where the participant ID matches the one we just got
        teamId = next(participant['teamId'] for participant in matchDict['participants'] if participant['participantId'] == participantId)

        # get the 'win' value for the next team that matches the team ID we just got, then see if it equals 'Win' because Riot is dumb and doesn't use a bool here and instead uses 'Win' or 'Fail'
        match.win = next(team['win'] for team in matchDict['teams'] if team['teamId'] == teamId) == 'Win'

    return matches

def createDayLookup(matches):
    # build up two different dicts, one holding the total matches played on a given day and one holding the wins
    # could probably do this as a running avg but I don't want to think that hard rn
    matchesByDay = defaultdict(int)
    winsByDay = defaultdict(int)
    for match in matches:
        day = match.date.strftime("%A")
        matchesByDay[day] += 1
        if match.win:
            winsByDay[day] += 1

    winPercentByDay = {}
    for day in matchesByDay:
        winPercentByDay[day] = '{0:.2%}'.format(winsByDay[day]/matchesByDay[day])

    # originally was gonna have this return the dict and do some nice charts and graphs but I'll save that for another day
    print(winPercentByDay)

if __name__ == '__main__':
    main()