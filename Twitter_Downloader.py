# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import time
import json
import re
from os import listdir, mkdir, system
from stopwords import stopWords
import requests
from datetime import datetime

try:
    import tweepy
except:
    system("pip install tweepy")  # windows
    import tweepy
try:
    from wordcloud import WordCloud
except:
    system("pip install wordcloud")  # windows
    from wordcloud import WordCloud
try:
    from arrow import Arrow
except:
    system("pip install arrow")  # windows
    from arrow import Arrow


def generateAPI(credentials_filename: str = "auth.json"):
    # open credentials
    with open(credentials_filename, "r") as auth:
        credentials = json.load(auth)
    consumerKey = credentials["consumer_key"]
    consumerSecret = credentials["consumer_secret"]
    accessToken = credentials["access_token"]
    accessTokenSecret = credentials["access_token_secret"]

    # criar o "objeto" de autenticação
    authenticate = tweepy.OAuthHandler(consumerKey, consumerSecret)

    # setar access token e access token secret
    authenticate.set_access_token(accessToken, accessTokenSecret)

    # Criar o objeto API
    api = tweepy.API(authenticate, wait_on_rate_limit=True)

    return api

# class Status: tweepy.models.Status


class Tweet():
    def __init__(self, status_json):
        self.metadata = status_json
        self.id = status_json["id"]
        self.userName = status_json["user"]["screen_name"]
        self.userID = status_json["user"]["id"]
        # creation converts, e.g. "Thu May 25 15:18:25 +0000 2017" to int timestamp
        self.creation = Arrow.strptime(status_json["created_at"], "%a %b %d %H:%M:%S %z %Y").timestamp
        self.text = status_json["full_text"]
        # source converts the html "a" tag string to its inner text
        self.source = re.search(">.*?<", status_json["source"])[0].strip("><")
        self.favoriteCount = status_json["favorite_count"]
        self.retweets = status_json["retweet_count"]
        self.language = status_json["lang"]
        self.mentions = self.getMentions()
        self.hashtags = self.getHashtags()
        self.url = self.getUrls()
        self.medias = self.getMedia()

        self.filename = datetime.strftime(
            datetime.utcfromtimestamp(self.creation), "%Y-%m-%d_%H-%M-%S_UTC")

    # getters
    def getMentions(self) -> list:
        """Searches for mentions inside status' json content"""
        if self.metadata["entities"]["user_mentions"]:
            return [mention["screen_name"] for mention in self.metadata["entities"]["user_mentions"]]

    def getHashtags(self) -> list:
        """Searches for hashtags inside status' json content"""
        if self.metadata["entities"]["hashtags"]:
            return [hashtag['text'] for hashtag in self.metadata["entities"]["hashtags"]]

    def getUrls(self) -> list:
        """Searches for shared urls inside status' json content"""
        if self.metadata["entities"]["urls"]:
            return [url["expanded_url"] for url in self.metadata["entities"]["urls"]]

    def getMedia(self) -> list:
        """Searches for shared media items inside target's status or target's retweeted status."""
        media_collection = []
        retweets_media_collection = []

        if "media" in self.metadata["entities"]:
            # if post has media files
            media_collection = loopOverMediaItems(self.metadata)
        elif "retweeted_status" in self.metadata:
            # if retweet has media files
            media_collection = loopOverMediaItems(
                self.metadata["retweeted_status"])
        else:
            # if no media at all
            return

        # if media and/or retweet's media
        return media_collection + [item for item in retweets_media_collection if item not in media_collection]

    def getText(self) -> str:
        """Searches for shared text inside target's status or target's retweeted status."""
        self.text = self.metadata["full_text"]
        if "retweeted_status" in self.metadata:
            self.text += "\n" + self.metadata["retweeted_status"]["full_text"]

    # downloaders
    def saveMedia(self):
        """Downlaod full list of media items."""
        assert_output(user_id=self.userName)
        for index, url in enumerate(self.medias):
            extension = re.search(r"\.[mjp][pn][4g]", url)[0]
            filename = f"{self.filename}_{index}"
            filePath = f".database/.{self.userName}/{filename}{extension}"
            mediaData = requests.get(url).content
            with open(filePath, "wb+") as handler:
                handler.write(mediaData)

    def saveTxt(self):
        assert_output(user_id=self.userName)
        txtPath = f".database/.{self.userName}/{self.filename}.txt"
        with open(txtPath, "w+", encoding="utf-8") as txtFile:
            txtFile.write(self.text)

    def saveMetadata(self):
        assert_output(user_id=self.userName)
        jsonPath = f".database/.{self.userName}/{self.filename}.json"
        with open(jsonPath, "w+", encoding="utf-8") as jsonPath:
            jsonPath.write(json.dumps(self.metadata))

    def to_dict(self):
        this_dict = {
            "ID": self.id,
            "User_Name": self.userName,
            "Created_At": self.creation,
            "Text": self.text,
            "Source": self.source,
            "Favorite_Count": self.favoriteCount,
            "Retweets": self.retweets,
            "Language": self.language
        }
        if self.mentions:
            this_dict["Mentions"] = self.mentions
        if self.hashtags:
            this_dict["Hashtags"] = self.hashtags
        if self.url:
            this_dict["Url"] = self.url
        if self.medias:
            this_dict["Media"] = self.medias
        return this_dict


class User():
    """Responsible for storing all downloaded and/or loaded from disk user data"""

    def __init__(self, screen_name):
        self.screenName: str = screen_name
        self.user_id: int
        self.description: str
        self.userName: str
        self.tweets: TweetList
        self._checkpoint: Checkpoint = Checkpoint(self.screenName)

    def save(self):
        self._checkpoint.saveCheckpoint(self.tweets)

    def load(self):
        self.tweets = self._checkpoint.loadCheckpoint()

    def fetchData(self, api: tweepy.API):
        pass

    def loadLatest(self):
        pass


class TweetList(list):
    """Responsible for dealing with list of tweet's metadata"""
    pass


class Checkpoint():
    """Responsible for loadings and savings such as loading """

    def __init__(self, userName: str):
        self.screen_name = userName

    def loadCheckpoint(self) -> list:
        """Tries to load all downloaded tweets from user's directory"""
        try:
            with open(f".database/.{self.screen_name}/user_data.checkpoint", 'r') as checkpointFile:
                backup = [json.loads(line)
                          for line in checkpointFile.readlines()]
        except:
            backup = []
        finally:
            return backup

    def saveCheckpoint(self, tweets_list: list):
        """
        Save all listed tweets in user's directory;\\
        Type of every list items is Tweet.
        """
        assert_output(self.screen_name)
        with open(f".database/.{self.screen_name}/user_data.checkpoint", "w+") as checkpointFile:
            checkpointFile.write(
                "\n".join([json.dumps(list_item.metadata) for list_item in tweets_list]))


def get_video_url(media):
    """Searches for the right video url."""
    for variant in media["video_info"]["variants"]:
        if variant['content_type'] == 'video/mp4':
            return variant["url"]


def assert_output(user_id: str):
    """Create output directory if needed."""
    if f".{user_id}" not in listdir(".database"):
        path = f".database/.{user_id}"
        mkdir(path)


def loopOverMediaItems(iterable_status: dict):
    local_collection = []
    for media in iterable_status["extended_entities"]["media"]:
        local_collection.append(media["media_url_https"])
        if media["type"] == "video" or media["type"] == "animated_gif":
            local_collection.append(get_video_url(media))
    return local_collection
