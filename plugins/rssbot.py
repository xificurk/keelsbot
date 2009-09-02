# -*- coding: utf-8 -*-
"""
    plugins/rssbot.py - A plugin for streaming RSS entries into a MUC.
    Copyright (C) 2007 Kevin Smith
    Copyright (C) 2009 Petr Morávek

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

import logging
import feedparser
import thread
import time
import re
import pickle

class rssbot(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = u"'RSSbot' umožňuje posílat do MUCu odkazy na nové položky z vybraných RSS kanálů.\nAutoři: Kevin Smith, Petr Morávek"

        self.workPath = "."
        path = self.config.find('work')
        if path != None and path.get('path', None) != None:
            self.workPath = path.get('path')
        self.rssCache = {}
        feeds = self.config.findall('feed')
        self.threads = {}
        self.shuttingDown = False
        if feeds:
            for feed in feeds:
                logging.info("rssbot.py script starting with feed %s." % feed.attrib['url'])
                roomsXml = feed.findall('muc')
                if not roomsXml:
                    continue
                rooms = []
                for roomXml in roomsXml:
                    rooms.append(roomXml.attrib['room'])
                logging.info("Creating new thread to manage feed.")
                self.threads[feed.attrib['url']] = thread.start_new(self.loop,(feed.attrib['url'], feed.attrib['refresh'], rooms))

    def shutDown(self):
        self.shuttingDown = True
        logging.info("Shutting down RSSBot plugin")

    def loop(self, feedUrl, refresh, rooms):
        """ The main thread loop that polls an rss feed with a specified frequency
        """
        self.loadCache(feedUrl)
        while not self.shuttingDown:
            if self.bot['xep_0045']:
                feed = feedparser.parse(feedUrl)
                if feedUrl not in self.rssCache.keys():
                    self.rssCache[feedUrl] = []
                tosend = {}
                for item in feed['entries']:
                    if item['link'] in self.rssCache[feedUrl]:
                        continue
                    tosend[item['title']] = item
                    self.rssCache[feedUrl].append(item['link'])

                titles = tosend.keys()
                titles.reverse()
                for title in titles:
                    for muc in rooms:
                        if muc in self.bot['xep_0045'].getJoinedRooms():
                            self.sendItem(tosend[title], muc, feed['channel']['title'])

                logging.debug("Saving updated feed cache for %s" % feedUrl)
                self.saveCache(feedUrl)

            time.sleep(float(refresh)*60)
            
    def sendItem(self, item, muc, feedName):
        """ Sends a summary of an rss item to a specified muc.
        """
        text = u"%s: %s\n%s" % (feedName, self.bot.xmlesc(item['title']), item['link'])
        self.bot.sendMessage(muc, text, mtype='groupchat')
    
    def cacheFilename(self, feedUrl):
        """ Returns the filename used to store the cache for a feedUrl
        """
        rep = re.compile('\W')
        return "%s/rsscache-%s.dat" % (self.workPath, rep.sub('', feedUrl))
    
    def loadCache(self, feed):
        """ Loads the cache of entries
        """
        try:
            f = open(self.cacheFilename(feed), 'rb')
            self.rssCache[feed] = pickle.load(f)
        except:
            print "Error loading rss data %s" % self.cacheFilename(feed)
            return
        f.close()
        
    def saveCache(self, feed):
        """ Saves the cache of entries
        """
        try:
            f = open(self.cacheFilename(feed), 'wb')
        except IOError:
            print "Error saving rss data %s" % cacheFilename(food)
            return
        pickle.dump(self.rssCache[feed], f)
        f.close()
