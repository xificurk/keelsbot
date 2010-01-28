# -*- coding: utf-8 -*-
"""
    plugins/seen.py - A plugin for tracking user sightings.
    Copyright (C) 2007 Kevin Smith
    Copyright (C) 2009-2010 Petr Morávek

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
import logging


class seen(object):
    def __init__(self, bot, config):
        self.log = logging.getLogger("keelsbot.seen")
        self.bot = bot
        self.store = seenStore(self.bot.store)
        self.about = "'Seen' umožňuje uživatelům ptát se, kdy naposledy byl někdo jiný viděn v MUCu.\nAutoři: Kevin Smith, Petr Morávek"
        bot.addCommand("seen", self.seen, "Naposledy viděn", "Kdy byl zadaný uživatel naposledy spatřen?", "seen nick")
        bot.add_event_handler("groupchat_presence", self.storePresence, threaded=True)
        bot.add_event_handler("groupchat_message", self.storeMessage, threaded=True)


    def storePresence(self, presence):
        """ Keep track of the presences in MUCs.
        """
        if presence.get("type", None) == "unavailable":
            pType = seenEvent.types["leave"]
        else:
            pType = seenEvent.types["presence"]
        self.store.update(seenEvent(presence["muc"].getNick(), presence["muc"].getRoom(), pType, datetime.datetime.now(), presence.get("status", None)))


    def storeMessage(self, message):
        """ Keep track of activity through messages.
        """
        if message["from"].full == message["mucroom"] or message["mucroom"] not in self.bot.rooms or self.bot.rooms[message["mucroom"]] == message["mucnick"] or "body" not in message.keys():
            return
        self.store.update(seenEvent(message["mucnick"], message["mucroom"], seenEvent.types["message"], datetime.datetime.now(), message.get("body", None)))


    def seen(self, command, args, msg):
        if args == None or args == "":
            return "Lamo! Musíš napsat, o kom chceš informace! ;-)"
        seenData = self.store.get(args)
        if seenData == None:
            return "{0}? Vůbec nevím, o kom je řeč...".format(args)

        sinceTime = datetime.datetime.now() - seenData.dateTime
        sinceTimeStr = self.formatTimeDiff(sinceTime)
        status = ""
        if seenData.type == seenEvent.types["message"]:
            status = ", když psal \"{0}\"".format(seenData.text)
        elif seenData.type == seenEvent.types["presence"] and seenData.text is not None:
            status = " ({0})".format(seenData.text)
        state = " v místnosti"
        if seenData.type == seenEvent.types["leave"]:
            state = ", jak opouští místnost"
        return "{0} byl naposledy spatřen{1} {2} před {3}{4}.".format(args, state, seenData.muc, sinceTimeStr, status)


    def formatTimeDiff(self, time):
        days = time.days
        seconds = time.seconds

        months = hours = minutes = 0
        response = ""

        months = int(days / 30)
        days -= months * 30
        if months > 0:
            if months == 1:
                monthsStr = "1 měsícem"
            else:
                monthsStr = "{0} měsíci".format(months)
            response = monthsStr

        if len(response) > 0 or days > 0:
            if days == 1:
                daysStr = "1 dnem"
            else:
                daysStr = "{0} dny".format(days)
            if len(response) > 0:
                return response + " a " + daysStr
            response = daysStr

        hours = int(seconds / 3600)
        seconds -= hours * 3600
        if len(response) > 0 or hours > 0:
            if hours == 1:
                hoursStr = "1 hodinou"
            else:
                hoursStr = "{0} hodinami".format(hours)
            if len(response) > 0:
                return response + " a " + hoursStr
            response = hoursStr

        minutes = int(seconds / 60)
        seconds -= minutes * 60
        if len(response) > 0 or minutes > 0:
            if minutes == 1:
                minutesStr = "1 minutou"
            else:
                minutesStr = "{0} minutami".format(minutes)
            if len(response) > 0:
                return response + " a " + minutesStr
            response = minutesStr

        if len(response) > 0 or seconds > 0:
            if seconds == 1:
                secondsStr = "1 sekundou"
            else:
                secondsStr = "{0} sekundami".format(seconds)
            if len(response) > 0:
                return response + " a " + secondsStr
            return secondsStr


    def shutDown(self):
        self.bot.del_event_handler("groupchat_presence", self.storePresence, threaded=True)
        self.bot.del_event_handler("groupchat_message", self.storeMessage, threaded=True)



class seenStore(object):
    def __init__(self, store):
        self.log = logging.getLogger("keelsbot.seen.store")
        self.store = store
        self.createTables()


    def createTables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS seen (
                        nick VARCHAR(256) NOT NULL PRIMARY KEY,
                        muc VARCHAR(256) NOT NULL,
                        type INTEGER(1) NOT NULL,
                        dateTime DATETIME,
                        text VARCHAR(256))""")


    def update(self, event):
        self.log.debug("Updating seen record for '{0}'.".format(event.nick))
        self.store.query("INSERT OR REPLACE INTO seen (nick, muc, type, dateTime, text) VALUES(?,?,?,?,?)", (event.nick, event.muc, event.type, event.dateTime, event.text))


    def get(self, nick):
        results = self.store.query("SELECT * FROM seen WHERE nick=?", (nick,))
        if len(results) == 0:
            return None
        result = results[0]
        return seenEvent(result["nick"], result["muc"], result["type"], datetime.datetime.strptime(result["dateTime"][0:19], "%Y-%m-%d %H:%M:%S"), result["text"])



class seenEvent(object):
    """ Represent the last known activity of a user.
    """
    types = {"message":1, "presence":2, "leave":3}

    def __init__(self, nick, muc, type, dateTime, text=None):
        self.nick = nick
        self.muc = muc
        self.dateTime = dateTime
        self.type = type
        self.text = text
