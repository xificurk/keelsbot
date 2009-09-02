# -*- coding: utf-8 -*-
"""
    plugins/seen.py - A plugin for tracking user sightings.
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

import datetime
import time
import logging

class seenevent(object):
    """ Represent the last know activity of a user.
    """
    messageType = 0
    joinType = 1
    partType = 2
    presenceType = 3
    
    def __init__(self, nick, eventTime, muc, stanzaType, text=None):
        """ Initialise seenevent 
        """
        self.nick = nick
        self.eventTime = eventTime
        self.muc = muc
        self.stanzaType = stanzaType
        self.text = text

class jidevent(object):
    """ Represent the last seen jid of a user.
    """
    def __init__(self, muc, nick, jid, eventTime):
        """Create event"""
        self.muc = muc
        self.nick = nick
        self.jid = jid
        self.eventTime = eventTime

class jidstore(object):
    def __init__(self, store):
        self.store = store
        self.createTable()

    def createTable(self):
        db = self.store.getDb()
        if not len(db.execute("pragma table_info('whowas')").fetchall()) > 0:
            db.execute("""CREATE TABLE whowas (
                       id INTEGER PRIMARY KEY AUTOINCREMENT, muc VARCHAR(256),
                       nick VARCHAR(256), jid VARCHAR(256), eventTime DATETIME)""")
        db.close()

    def update(self, event):
        db = self.store.getDb()
        cur = db.cursor()
        logging.debug("Updating whowas")
        cur.execute('SELECT * FROM whowas WHERE nick=? AND muc=?', (event.nick,event.muc))
        if (len(cur.fetchall()) > 0):
            cur.execute('UPDATE whowas SET jid=?, eventTime=?', (event.jid, event.eventTime))
            logging.debug("Updated existing whowas")
        else:
            cur.execute('INSERT INTO whowas(nick, muc, jid, eventTime) VALUES(?,?,?,?)',(event.nick, event.muc, event.jid, event.eventTime))
            logging.debug("Added new whowas")
        db.commit()
        db.close()


    def get(self, nick, muc):
        db = self.store.getDb()
        cur = db.cursor()
        cur.execute('SELECT * FROM seen WHERE nick=? AND muc=?', (nick,muc))
        results = cur.fetchall()
        if len(results) == 0:
            return None
        return jidevent(results[0][1],results[0][2],results[0][3],datetime.datetime.strptime(results[0][4][0:19],"""%Y-%m-%d %H:%M:%S""" ))
        db.close()

    def delete(self, nick, muc):
        db = self.store.getDb()
        cur = db.cursor()
        cur.execute('DELETE FROM seen WHERE nick=? AND muc=?', (nick,muc))
        db.commit()
        db.close()

class seenstore(object):
    def __init__(self, store):
        #self.null = None
        #self.data = {}
        #self.loaddefault()
        self.store = store
        self.createTable()
      
    def createTable(self):
        db = self.store.getDb()
        #Yes, I know this is completely denormalised, and if it becomes more complex I'll refactor the schema
        if not len(db.execute("pragma table_info('seen')").fetchall()) > 0:
            db.execute("""CREATE TABLE seen (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       nick VARCHAR(256), eventTime DATETIME, muc VARCHAR(256), stanzaType INTEGER, text VARCHAR(256))""")
        #if len(db.execute("pragma table_info('seen')").fetchall()) == 6:
        #    db.execute("""ALTER TABLE seen ADD COLUMN fullJid VARCHAR(256)""")
        db.close()
    
    def update(self, event):
        db = self.store.getDb()
        cur = db.cursor()
        logging.debug("Updating seen")
        cur.execute('SELECT * FROM seen WHERE nick=?', (event.nick,))
        if (len(cur.fetchall()) > 0):
            cur.execute('UPDATE seen SET nick=?, eventTime=?, muc=?, stanzaType=?, text=? WHERE nick=?', (event.nick, event.eventTime, event.muc, event.stanzaType, event.text, event.nick))
            logging.debug("Updated existing seen")
        else:
            cur.execute('INSERT INTO seen(nick, eventTime, muc, stanzaType, text) VALUES(?,?,?,?,?)',(event.nick, event.eventTime, event.muc, event.stanzaType, event.text))
            logging.debug("Added new seen")
        db.commit()
        db.close()

        
    def get(self, nick):
        db = self.store.getDb()
        cur = db.cursor()
        cur.execute('SELECT * FROM seen WHERE nick=?', (nick,))
        results = cur.fetchall()
        if len(results) == 0:
            return None
        return seenevent(results[0][1],datetime.datetime.strptime(results[0][2][0:19],"""%Y-%m-%d %H:%M:%S""" ),results[0][3],results[0][4],results[0][5])
        db.close()
        
    def delete(self, nick):
        db = self.store.getDb()
        cur = db.cursor()
        cur.execute('DELETE FROM seen WHERE nick=?', (nick,))
        db.commit()
        db.close()
    
class seen(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.seenstore = seenstore(self.bot.store)
        self.about = u"'Seen' umožňuje uživatelům ptát se, kdy naposledy byl někdo jiný iděn v MUCu.\nAutoři: Kevin Smith, Petr Morávek"
        self.bot.addCommand(u'seen', self.handle_seen_request, u'Naposledy viděn', u"Kdy byl zadaný uživatel naposledy spatřen?", u'seen nick')
        self.bot.add_event_handler("groupchat_presence", self.handle_groupchat_presence, threaded=True)
        self.bot.add_event_handler("groupchat_message", self.handle_groupchat_message, threaded=True)

    def handle_groupchat_presence(self, presence):
        """ Keep track of the presences in mucs.
        """
        presence['dateTime'] = datetime.datetime.now()
        if presence.get('type', None) == 'unavailable':
            pType = seenevent.partType
        else:
            pType = seenevent.presenceType
        self.seenstore.update(seenevent(presence['nick'], presence['dateTime'], presence['room'], pType, presence.get('status', None)))

    def handle_groupchat_message(self, message):
        """ Keep track of activity through messages.
        """
        if 'message' not in message.keys():
            return
        message['dateTime'] = datetime.datetime.now()
        self.seenstore.update(seenevent(message['name'], message['dateTime'], message['room'], seenevent.messageType, message['message']))

    def getStringTime(self, time):
        days = time.days
        seconds = time.seconds
        
        months = hours = minutes = 0
        response = ""

        months = days / 30
        days -= months * 30
        if months > 0:
            if months == 1:
                months_str = u"1 měsícem"
            else:
                months_str = u"%d měsíci" % months
            response += months_str

        if len(response) > 0 or days > 0:
            if days == 1:
                days_str = "1 dnem"
            else:
                days_str = "%d dny" % days
            if len(response) > 0:
                return response + " a " + days_str
            response += days_str

        hours = seconds / 3600
        seconds -= hours * 3600
        if len(response) > 0 or hours > 0:
            if hours == 1:
                hours_str = "1 hodinou"
            else:
                hours_str = "%d hodinami" % hours
            if len(response) > 0:
                return response + " a " + hours_str
            response += hours_str

        minutes = seconds / 60
        seconds -= minutes * 60
        if len(response) > 0 or minutes > 0:
            if minutes == 1:
                minutes_str = "1 minutou"
            else:
                minutes_str = "%d minutami" % minutes
            if len(response) > 0:
                return response + " a " + minutes_str
            response += minutes_str

        if len(response) > 0 or seconds > 0:
            if seconds == 1:
                seconds_str = "1 sekundou"
            else:
                seconds_str = "%d sekundami" % seconds
            if len(response) > 0:
                return response + " a " + seconds_str
            return seconds_str

    def handle_seen_request(self, command, args, msg):
        if args == None or args == "":
            return u"Lamo! Musíš napsat, o kom chceš informace! ;-)"
        seenData = self.seenstore.get(args)
        if seenData == None:
            return args + u"? Vůbec nevím, o kom je řeč..."

        sinceTime = datetime.datetime.now() - seenData.eventTime
        sinceTimeStr = self.getStringTime(sinceTime)
        status = ""
        if seenData.stanzaType == seenevent.messageType:
            status = u", když psal \"%s\"" % seenData.text
        elif seenData.stanzaType == seenevent.presenceType and seenData.text is not None:
            status = u" (%s)" % seenData.text
        state = u" v místnosti"
        if seenData.stanzaType == seenevent.partType:
            state = u", jak opouští místnost"
        return u"%s byl naposledy spatřen%s %s před %s%s."  %(args, state, seenData.muc, sinceTimeStr, status)

    def shutDown(self):
        self.bot.del_event_handler("groupchat_presence", self.handle_groupchat_presence, threaded=True)
        self.bot.del_event_handler("groupchat_message", self.handle_groupchat_message, threaded=True)
