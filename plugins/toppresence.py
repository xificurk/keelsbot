# -*- coding: utf-8 -*-
"""
    plugins/toppresence.py - A plugin for tracking current and maximum number
    of users in MUC.
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
import time


class toppresence(object):
    sleekDependencies = ["xep_0045"]

    def __init__(self, bot, config):
        self.log = logging.getLogger("keelsbot.toppresence")
        self.bot = bot
        self.store = toppresenceStore(self.bot.store)
        self.about = "'TopPresence' sleduje počet uživatelů v MUCu a hlásí, když je dosažen rekord.\nAutor: Petr Morávek"
        bot.addCommand("cu", self.current, "Počet uživatelů v MUCu", "Vypíše aktuální počet uživatelů v MUCu.", "cu")
        bot.addCommand("mu", self.maximum, "Maximální počet uživatelů v MUCu", "Vypíše historicky nejvyšší počet uživatelů v MUCu.", "mu")
        bot.add_event_handler("groupchat_presence", self.storePresence, threaded=True)


    def storePresence(self, presence):
        """ Keep track of the presences in MUCs.
        """
        if presence["type"] in ("error", "probe", "unavailable"):
            return
        muc = presence["muc"]["room"]
        if muc == None or muc not in self.bot.rooms:
            return
        self.log.debug(self.bot.plugin["xep_0045"].getRoster(muc))
        current = len(self.bot.plugin["xep_0045"].getRoster(muc))
        time.sleep(2)
        current = max(len(self.bot.plugin["xep_0045"].getRoster(muc)), current)

        if current > self.store.get(muc)[0]:
            self.store.update(muc, current)
            self.bot.sendMessage(muc, "V místnosti je historicky nejvyšší počet uživatelů ({0}).".format(current), mtype="groupchat")


    def current(self, command, args, msg):
        muc = msg["from"].bare
        if muc == None or muc not in self.bot.rooms:
            return

        current = len(self.bot.plugin["xep_0045"].getRoster(muc))
        return "Momentálně tu vidím {0} uživatelů.".format(current)


    def maximum(self, command, args, msg):
        muc = msg["from"].bare
        if muc == None or muc not in self.bot.rooms:
            return

        stored = self.store.get(muc)
        return "Nejvíc narváno tu bylo {1}.{2}.{3} v {4}, to jsem tu viděl {0} uživatelů.".format(stored[0], stored[1].day, stored[1].month, stored[1].year, stored[1].strftime("%H:%M"))


    def shutDown(self):
        self.bot.del_event_handler("groupchat_presence", self.storePresence)



class toppresenceStore(object):
    def __init__(self, store):
        self.log = logging.getLogger("keelsbot.toppresence.store")
        self.store = store
        self.createTables()


    def createTables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS toppresence (
                        muc VARCHAR(256) NOT NULL PRIMARY KEY,
                        users INTEGER(3) NOT NULL,
                        dateTime DATETIME)""")


    def update(self, muc, number):
        self.log.debug("Updating toppresnece record for '{0}'.".format(muc))
        self.store.query("INSERT OR REPLACE INTO toppresence (muc, users, dateTime) VALUES(?,?,?)", (muc, number, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


    def get(self, muc):
        results = self.store.query("SELECT * FROM toppresence WHERE muc=? LIMIT 1", (muc,))
        if len(results) == 0:
            return (0, "kdysi dávno")
        result = results[0]
        self.log.debug(result["dateTime"])
        return (result["users"], datetime.datetime.strptime(result["dateTime"][0:19], "%Y-%m-%d %H:%M:%S"))
