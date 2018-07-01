from hashlib import md5 as getMD5Hash
from datetime import timedelta, datetime
from sys import version_info as pythonVersion

from pyrez.http import HttpRequest as HttpRequest
from pyrez.enumerations import Endpoint, Platform, ResponseFormat, LanguageCode, Champions, Status, Tier
from pyrez.models import APIResponse, HiRezServerStatus, Champion, ChampionSkin, God, DataUsed, PlayerPaladins, PlayerStatus, PlayerSmite, Friend, GodRank, Session, PatchInfo, PaladinsItem, SmiteItem, PlayerLoadouts, MatchHistory
from pyrez.exceptions import CustomException, WrongCredentials, KeyOrAuthEmptyException, DailyLimitException, NotFoundException, SessionLimitException

class BaseAPI:
    """Class for all of the outgoing requests from the library. An instance of
    this is created by the Client class. Do not initialise this yourself.

    Parameters
    ----------
        devKey : str or int
            Develop ID used for authentication.
        authKey : str
            Authentication Key used for authentication.
        endpoint: str
        responseFormat: [optional] : str
        language: [optional] : int

    """
    def __init__ (self, devKey, authKey, endpoint, responseFormat = ResponseFormat.JSON, language = LanguageCode.ENGLISH):
        if not devKey or not authKey:
            raise KeyOrAuthEmptyException ("No DevKey or AuthKey specified!")
        elif len (str (devKey)) <= 3:
            raise NotFoundException ("No DevKey specified!")
        elif len (str (authKey)) < 30:
            raise NotFoundException ("No AuthKey specified!")
        elif len (str (endpoint)) == 0 :
            raise NotFoundException ("Endpoint can't be empty!")
        else:
            self.__devKey__ = devKey
            self.__authKey__ = authKey
            self.__endpointBaseURL__ = endpoint
            self.__responseFormat__ = responseFormat if (responseFormat == ResponseFormat.JSON or responseFormat == ResponseFormat.XML) else ResponseFormat.JSON
            self.__language__ = int (language) if language else int (LanguageCode.ENGLISH)
    def __encode__ (self, string, encodeType = "utf-8"):
        return str (string).encode (encodeType)
    def __decode__ (self, string, encodeType = "utf-8"):
        return str (string).encode (encodeType)

class HiRezAPI (BaseAPI):
    __header__ = { "user-agent": "PyRez [Python/{0.major}.{0.minor}]".format (pythonVersion) }

    def __init__ (self, devKey, authKey, endpoint, responseFormat = ResponseFormat.JSON, language = LanguageCode.ENGLISH):
        super ().__init__ (devKey, authKey, endpoint, responseFormat, language)
        self.__lastSession__ = None
        self.getLanguage = self.__language__

    def __createTimeStamp__ (self, format = "%Y%m%d%H%M%S"):
        return self.__currentTime__ ().strftime (format)

    def __currentTime__ (self):
        return datetime.utcnow ()

    def __createSignature__ (self, method):
        return getMD5Hash (self.__encode__ (self.__devKey__) + self.__encode__ (method) + self.__encode__ (self.__authKey__) + self.__encode__ (self.__createTimeStamp__ ())).hexdigest ()

    def __sessionExpired__ (self):
        return self.__lastSession__ is None or self.__currentTime__ () - self.__lastSession__ >= timedelta (minutes = 15)

    def __createSession__ (self):
        try:
            request = self.makeRequest ("createsession")
            if request:
                self.currentSession = Session (** request)
                self.__lastSession__ = self.__currentTime__( )
        except WrongCredentials as x:
            raise x

    def makeRequest (self, apiMethod, params = ()):
        if len (str (apiMethod)) == 0:
            raise NotFoundException ("No API method specified!")
        elif (apiMethod.lower () != "createsession" and self.__sessionExpired__ ()):
            self.__createSession__ ()
        result = HttpRequest (self.__header__).get (self.__buildUrlRequest__ (apiMethod.lower (), params))
        if result.status_code == 200:
            jsonResult = result.json ()
            if len (jsonResult) == 0:
                raise NotFoundException ("Not found!")
            else:
                if apiMethod.lower () == "testsession" or apiMethod.lower () == "ping":
                    return jsonResult
                else:
                    foundProblem = False
                    errorMessage = ""
                    hasError = APIResponse (** jsonResult) if apiMethod.lower () == "createsession" or apiMethod.lower () == "getpatchinfo" else APIResponse (** jsonResult [0])
                    if hasError != None and hasError.retMsg != None:
                        if hasError.retMsg.lower () != "approved":
                            foundProblem = not foundProblem
                            errorMessage = hasError.retMsg

                            if errorMessage.find ("dailylimit") != -1:
                                raise DailyLimitException ("Daily limit reached: " + errorMessage)
                            elif errorMessage.find ("Maximum number of active sessions reached") != -1:
                                raise SessionLimitException ("Concurrent sessions limit reached: " + errorMessage)
                            elif errorMessage.find ("Invalid session id") != -1:
                                self.__createSession__ ()
                                self.makeRequest (apiMethod, params)
                            elif errorMessage.find ("Exception while validating developer access") != -1:
                                raise WrongCredentials ("Wrong credentials: " + errorMessage)
                            elif errorMessage.find ("404") != -1:
                                raise NotFoundException ("Not found: " + errorMessage)
                    if not foundProblem:
                        return jsonResult
        elif result.status_code == 404:
            raise NotFoundException ("Wrong URL: " + result.text)

    def __buildUrlRequest__ (self, apiMethod, params = ()):
        if len (str (apiMethod)) == 0:
            raise NotFoundException ("No API method specified!")
        else:
            urlRequest = "{0}/{1}{2}".format (self.__endpointBaseURL__, apiMethod, self.__responseFormat__)
            if apiMethod.lower () != "ping":
                urlRequest += "/{0}/{1}".format (self.__devKey__, self.__createSignature__ (apiMethod))
                if apiMethod.lower () != "createsession" and self.currentSession != None:
                    urlRequest += "/{0}".format (self.currentSession.sessionID)
                urlRequest += "/{0}".format (self.__createTimeStamp__ ())
        
                if params:
                    for param in params:
                        if param != None:
                            urlRequest += "/" + str (param)
            return urlRequest

    def ping (self):
        return self.makeRequest ("ping")

    def testSession (self):
        return self.makeRequest ("testsession")

    def getDataUsed (self):
        return DataUsed (** self.makeRequest ("getdataused") [0])

    def getDemoDetails (self, matchID):
        return self.makeRequest ("getdemodetails", [matchID])

    def getEsportsProLeagueDetails (self):
        return self.makeRequest ("getesportsproleaguedetails")

    def getFriends (self, playerID):
        if (len (playerID) <= 3):
            raise NotFoundException ("Invalid player!")
        else:
            friendsRequest = self.makeRequest ("getfriends", [playerID])
            friends = []
            for friend in friendsRequest:
                friends.append (Friend (** friend))
            return friends if friends else None

    def getGods (self, language = None):
        if language  and int (self.__language__) != int (language):
            self.__language__ = language
        godsRequest = self.makeRequest ("getgods", [self.__language__])
        if not godsRequest:
            return None
        else:
            gods = []
            for i in godsRequest:
                if i ["id"] == "0":
                    continue
                obj = God (** i) if isinstance (self, SmiteAPI) != -1 else Champion (** i)
                gods.append (obj)
            return gods if gods else None
    
    def getGodRanks (self, playerID):
        if (len (playerID) <= 3):
            raise NotFoundException ("Invalid player!")
        godRanksRequest = self.makeRequest ("getgodranks", [playerID])
        if not godRanksRequest:
            return None
        else:
            godRanks = []
            for i in godRanksRequest:
                obj = GodRank (** i)
                godRanks.append (obj)
            return godRanks if godRanks else None

    def getGodRecommendedItems (self, godID):
        return self.makeRequest ("getgodrecommendeditems", [godID])

    def getGodSkins (self, godID):
        return self.makeRequest ("getgodskins", [godID])

    def getHiRezServerStatus (self):
        return HiRezServerStatus (** self.makeRequest ("gethirezserverstatus") [0])

    def getItems (self, language = None):
        if language and int (self.__language__) != int (language):
            self.__language__ = language
        return self.makeRequest ("getitems", [language])

    def getLeagueLeaderboard (self, queueID, tier, season):
        return self.makeRequest ("getleagueleaderboard", [queueID, tier, season])

    def getLeagueSeasons (self, queueID):
        return self.makeRequest ("getleagueseasons", [queueID])

    def getMatchDetails (self, matchID):
        return self.makeRequest ("getmatchdetails", [matchID])

    def getMatchHistory (self, playerID):
        # /getplayerloadouts[ResponseFormat]/{developerId}/{signature}/{session}/{timestamp}/playerId}/{languageCode}
        if (len (playerID) <= 3):
            raise NotFoundException ("Invalid player!")
        matchHistoryRequest = self.makeRequest ("getmatchhistory", [playerID])
        if not matchHistoryRequest:
            return None
        else:
            matchHistorys = []
            for i in range (0, len (matchHistoryRequest)):
                obj = MatchHistory (** matchHistoryRequest [i])
                matchHistorys.append (obj)
            return matchHistorys if matchHistorys else None

    def getMatchIdsByQueue (self, queueID, date, hour = -1):
        return self.makeRequest ("getmatchidsbyqueue", [queueID, date, hour])

    def getMatchPlayerDetails (self, matchID):
        return self.makeRequest ("getmatchplayerdetails", [matchID])

    def getMotd (self):
        return self.makeRequest ("getmotd")

    def getPatchInfo (self):
        res = self.makeRequest ("getpatchinfo")
        return PatchInfo (** res) if res else None

    def getPlayer (self, playerID, useHiRez = True):
        if (len (playerID) <= 3):
            raise NotFoundException ("Invalid player!")
        else:
            if isinstance (self, RealmRoyaleAPI):
                return self.makeRequest ("getplayer", [playerID, "hirez" if useHiRez else "steam"])
            else:
                res = self.makeRequest ("getplayer", [playerID]) [0]
                return PlayerSmite (** res) if isinstance (self, SmiteAPI) else PlayerPaladins (** res)

    def getPlayerAchievements (self, playerID):
        if (len (playerID) <= 3):
            raise NotFoundException ("Invalid player!")
        return self.makeRequest ("getplayerachievements", [playerID])

    def getPlayerLoadouts (self, playerID, language = None):
        if isinstance (self, PaladinsAPI):
            if language and int (self.__language__) != int (language):
                self.__language__ = language
            playerLoadoutRequest = self.makeRequest ("getplayerloadouts", [playerID, self.__language__])
            if not playerLoadoutRequest:
                return None
            else:
                playerLoadouts = []
                for i in range (0, len (playerLoadoutRequest)):
                    obj = PlayerLoadouts (** playerLoadoutRequest [i])
                    playerLoadouts.append (obj)
                return playerLoadouts if playerLoadouts else None
        else:
            raise NotFoundException ("PALADINS ONLY")

    def getPlayerStatus (self, playerID):
        if (len (playerID) <= 3):
            raise NotFoundException ("Invalid player!")
        return PlayerStatus (** self.makeRequest ("getplayerstatus", [playerID]) [0])

    def getQueueStats (self, playerID, queueID):
        if (len (playerID) <= 3):
            raise NotFoundException ("Invalid player!")
        return self.makeRequest ("getqueuestats", [playerID, queueID])

    def getTeamDetails (self, clanID):
        return self.makeRequest ("getteamdetails", [clanID])

    def getTeamMatchHistory (self, clanID):
        return self.makeRequest ("getteammatchhistory", [clanID])

    def getTeamPlayers (self, clanID):
        return self.makeRequest ("getteamplayers", [clanID])

    def getTopMatches (self):
        return self.makeRequest ("gettopmatches")

    def searchTeams (self, teamID):
        return self.makeRequest ("searchteams", [teamID])

    def setEndpoint (self, endpoint):
        if endpoint != self.__endpointBaseURL__ and len (str (endpoint)) > 0:
            super ().__init__ (self.__devKey__, self.__authKey__, endpoint, self.__responseFormat__, self.__language__)

class PaladinsAPI (HiRezAPI):
    def __init__ (self, devKey, authKey, platform = Endpoint.PALADINS_PC, responseFormat = ResponseFormat.JSON, language = LanguageCode.ENGLISH):
        endpoint = Endpoint.PALADINS_XBOX if (platform == Platform.XBOX) else Endpoint.PALADINS_PS4 if (platform == Platform.PS4) else Endpoint.PALADINS_PC
        super ().__init__ (devKey, authKey, endpoint, responseFormat, language)

class SmiteAPI (HiRezAPI):
    def __init__ (self, devKey, authKey, platform = Endpoint.SMITE_PC, responseFormat = ResponseFormat.JSON, language = LanguageCode.ENGLISH):
        endpoint = Endpoint.SMITE_XBOX if (platform == Platform.XBOX) else Endpoint.SMITE_PS4 if (platform == Platform.PS4) else Endpoint.SMITE_PC
        super ().__init__ (devKey, authKey, endpoint, responseFormat, language)

class RealmRoyaleAPI (HiRezAPI):
    def __init__ (self, devKey, authKey, responseFormat = ResponseFormat.JSON, language = LanguageCode.ENGLISH):
        super ().__init__ (devKey, authKey, Endpoint.REALM_ROYALE_PC, responseFormat, language)