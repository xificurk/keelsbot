# -*- coding: utf-8 -*-
"""
    plugins/feedreader.py -  A plugin for streaming feed entries (RSS etc.)
    into a MUC.
    Copyright (C) 2010 Petr Morávek

    This file is part of KeelsBot.

    Keelsbot is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    KeelsBot is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

from html.parser import HTMLParser
import datetime
import logging
import random
import threading
import time
import urllib.request
from xml.etree import cElementTree as ET


class feedreader(object):
    def __init__(self, bot, config):
        self.log = logging.getLogger("keelsbot.feedreader")
        self.bot = bot
        self.about = "'FeedReader' umožňuje posílat do MUCu, nebo zadaným JID odkazy na nové položky z vybraných RSS kanálů.\nAutor: Petr Morávek"
        self.store = feedStore(self.bot.store)
        self.shuttingDown = False
        for feed in config.findall("feed"):
            url = feed.get("url")
            if url is None:
                self.log.error("No feed url given.")
                continue

            refresh = feed.get("refresh", 60)

            subscribers = []
            for subscriber in feed.findall("subscriber"):
                jid = subscriber.get("jid")
                if jid is None:
                    self.log.error("Subscriber element missing jid attribute.")
                    continue
                type = subscriber.get("type", "groupchat")
                subscribers.append((jid, type))

            threading.Thread(target=self.loop, args=(url, refresh, subscribers)).start()


    def shutDown(self):
        self.shuttingDown = True


    def loop(self, url, refresh, subscribers):
        """ The main thread loop that polls an rss feed with a specified frequency
        """
        self.log.debug("Starting loop for feed {0} (refresh rate {1}min)".format(url, refresh))
        refresh = float(refresh)*60
        salt = random.random() * refresh / 100
        refresh = refresh + salt
        parser = feedParser(url)
        known = self.store.get(url)
        while not self.shuttingDown:
            parser.check()
            sent = []
            for item in parser.items:
                link = item.get("link", "")
                title = item.get("title", "")
                if link not in known:
                    self.log.debug("Found new ittem '{0}' in feed {1}.".format(title, parser.channel["title"]))
                    wait = 0
                    if title not in sent:
                        self.send(subscribers, parser.channel, item)
                        sent.append(title)
                        wait = 1
                    self.store.add(url, link)
                    known.append(link)
                    time.sleep(wait)
            time.sleep(refresh)


    def send(self, subscribers, channel, item):
        """ Sends a summary of an feed item to a specified JID.
        """
        text = "{0}: {1}\n{2}".format(channel["title"], item.get("title"), item.get("link"))
        for subscriber in subscribers:
            if subscriber[1] == "groupchat" and subscriber[0] not in self.bot.rooms:
                continue
            self.bot.sendMessage(subscriber[0], text, mtype=subscriber[1])



class feedStore(object):
    def __init__(self, store):
        self.log = logging.getLogger("keelsbot.feedreader.store")
        self.store = store
        self.createTables()


    def createTables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS feedItems (
                        feed VARCHAR(256) NOT NULL,
                        item VARCHAR(256) NOT NULL,
                        dateTime DATETIME NOT NULL,
                        PRIMARY KEY (feed, item))""")


    def add(self, feed, item):
        self.log.debug("Storing new item {0} in feed {1}.".format(item, feed))
        self.store.query("INSERT OR REPLACE INTO feedItems (feed, item, dateTime) VALUES(?,?,?)", (feed, item, datetime.datetime.now()))


    def get(self, feed):
        for row in self.store.query("SELECT item FROM feedItems WHERE feed=? ORDER BY dateTime DESC LIMIT 100, 10000", (feed,)):
            self.store.query("DELETE FROM feedItems WHERE feed=? AND item=?", (feed, row["item"]))
        items = []
        for row in self.store.query("SELECT item FROM feedItems WHERE feed=?", (feed,)):
            items.append(row["item"])
        return items



class feedParser:
    __unescape = HTMLParser().unescape

    def __init__(self, url):
        self.log = logging.getLogger("keelsbot.feedreader.parser")

        self.url = url
        self.data = None
        self.xml = None

        self.channel = {"title":"", "description":"", "link":self.url}
        self.items = []


    def check(self):
        self.fetch()
        self.parse()


    def fetch(self):
        try:
            response = urllib.request.urlopen(self.url, timeout=10)
        except IOError:
            self.log.error("Could not fetch URL {0}.".format(self.url))
            return
        if response.getcode() != 200:
            self.log.error("Got error code {0} while fetching {1}.".format(response.getcode(), self.url))
            return
        self.data = response


    def parse(self):
        if self.data is None:
            self.log.error("No data to parse from feed {0}.".format(self.url))
            return

        xml = ET.parse(self.data).find("/channel")
        self.xml = xml

        for element in xml.getchildren():
            if element.tag != "item":
                self.channel[element.tag] = self.unescape(element.text).strip()

        self.items = []
        for item in xml.findall("item"):
            values = {}
            for element in item.getchildren():
                values[element.tag] = self.unescape(element.text).strip()
            self.items.append(values)


    def unescape(self, text):
        """Unescape HTML entities"""
        if text is None:
            return ""
        return self.__unescape(text)
