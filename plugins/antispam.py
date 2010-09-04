# -*- coding: utf-8 -*-
"""
    plugins/antispam.py - MUC antispam plugin.
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

import logging
import time
from xml.etree import cElementTree as ET


class antispam(object):
    sleekDependencies = ["xep_0045"]

    def __init__(self, bot, config):
        self.log = logging.getLogger("keelsbot.antispam")
        self.bot = bot
        self.about = "'Antispam' hlídá MUC proti spamu - spammera varuje, kickne, případně zabanuje.\nAutor: Petr Morávek"
        self.badBoys = {}
        self.history = {}

        self.config = {}
        for muc in config.findall("muc"):
            room = muc.get("room")
            if room is None:
                self.log.error("Configuration error - room attribute required.")
                continue

            noban = False
            if muc.get("noban") is not None:
                noban = True

            message = muc.find("message")
            if message is not None:
                interval = message.get("interval")
                limit = message.get("limit")
                remember = message.get("remember")
                if interval is None or limit is None or remember is None:
                    self.log.error("Configuration error (message limit).")
                    message = None
                else:
                    message = {"interval":int(interval), "limit":int(limit), "remember":int(remember)}

            character = muc.find("character")
            if character is not None:
                interval = character.get("interval")
                limit = character.get("limit")
                remember = character.get("remember")
                if interval is None or limit is None or remember is None:
                    self.log.error("Configuration error (character limit).")
                    character = None
                else:
                    character = {"interval":int(interval), "limit":int(limit), "remember":int(remember)}

            if message is None and character is None:
                self.log.error("Configuration error - no limits given.")
            else:
                self.log.info("Enabling spam protection in romm {0}.".format(room))
                self.config[room] = {"noban":noban}
                self.badBoys[room] = {}
                self.history[room] = []

            if message is not None:
                self.config[room]["message"] = message
            if character is not None:
                self.config[room]["character"] = character

        bot.add_event_handler("groupchat_message", self.checkSpam, threaded=False)


    def checkSpam(self, message):
        """ Keep track of activity through messages.
        """
        if message["type"] != "groupchat":
            return

        room = message["mucroom"]
        nick = message["mucnick"]

        if room not in self.config or message["from"].full == room or room not in self.bot.rooms or self.bot.rooms[room] == nick or "body" not in message.keys():
            # no antispam, system msg, not joined, own msg, or invalid
            return

        botRole = self.bot.plugin["xep_0045"].getJidProperty(room, self.bot.rooms[room], "role")
        if botRole != "moderator":
            # We don't have rights
            return

        nickRole = self.bot.plugin["xep_0045"].getJidProperty(room, nick, "role")
        botAffiliation = self.bot.plugin["xep_0045"].getJidProperty(room, self.bot.rooms[room], "affiliation")
        nickAffiliation = self.bot.plugin["xep_0045"].getJidProperty(room, nick, "affiliation")
        if nickAffiliation == "owner" or (nickAffiliation == "admin" and botAffiliation != "owner") or (nickRole == "moderator" and botAffiliation not in ("admin", "owner")):
            # Power user
            return

        jid = str(self.bot.plugin["xep_0045"].getJidProperty(room, nick, "jid"))
        now = int(time.time())
        config = self.config[room]
        history = self.history[room]
        badBoys = self.badBoys[room]
        history.append((now, jid, len(message.get("body", ""))))

        maxInterval = 0
        maxRemember = 0
        action = None

        conf = config.get("message")
        if conf is not None:
            maxInterval = max(maxInterval, conf["interval"])
            maxRemember = max(maxRemember, conf["remember"])
            count = 0
            age = now - conf["interval"]
            for row in history:
                if row[1] == jid and row[0] >= age:
                    count = count + 1
            if count >= conf["limit"]:
                age = now - conf["remember"]
                if jid not in badBoys or badBoys[jid][0] < age:
                    action = "warn"
                    self.warn(room, nick)
                elif badBoys[jid][1] == "warn":
                    action = "kick"
                    self.kick(room, jid)
                else:
                    action = "ban"
                    if config["noban"]:
                        self.kick(room, jid)
                    else:
                        self.ban(room, jid)
                badBoys[jid] = (now, action)

        conf = config.get("character")
        if conf is not None:
            maxInterval = max(maxInterval, conf["interval"])
            maxRemember = max(maxRemember, conf["remember"])
            if action is None:
                count = 0
                age = now - conf["interval"]
                for row in history:
                    if row[1] == jid and row[0] >= age:
                        count = count + row[2]
                if count >= conf["limit"]:
                    age = now - conf["remember"]
                    if jid not in badBoys or badBoys[jid][0] < age:
                        action = "warn"
                        self.warn(room, nick)
                    elif badBoys[jid][1] == "warn":
                        action = "kick"
                        self.kick(room, jid)
                    else:
                        action = "ban"
                        if config["noban"]:
                            self.kick(room, jid)
                        else:
                            self.ban(room, jid)
                    badBoys[jid] = (now, action)

        for row in list(history):
            if row[0] < (now - maxInterval):
                history.remove(row)
            else:
                break
        for jid in list(badBoys.keys()):
            if badBoys[jid][0] < (now - maxRemember):
                del badBoys[jid]
        self.log.debug("Got {0} in history and {1} badBoys.".format(len(history), len(badBoys)))


    def warn(self, room, nick):
        """ Warn user not to spam.
        """
        self.log.info("Warning '{0}' in room {1}.".format(nick, room))
        self.bot.sendMessage(room, "{0}: Nespamuj!".format(nick), mtype="groupchat")
        return True


    def kick(self, room, jid):
        """ Kick a nick from a room.
        """
        self.log.info("Kicking '{0}' from room {1}.".format(jid, room))
        query = ET.Element("{http://jabber.org/protocol/muc#admin}query")
        item = ET.Element("item", {"role":"none", "jid":jid})
        reason = ET.Element("reason")
        reason.text = "spam"
        item.append(reason)
        query.append(item)
        iq = self.bot.makeIqSet(query)
        iq["to"] = room
        result = iq.send()
        return True


    def ban(self, room, jid):
        """ Ban a nick from a room.
        """
        botAffiliation = self.bot.plugin["xep_0045"].getJidProperty(room, self.bot.rooms[room], "affiliation")
        if botAffiliation not in ("admin", "owner"):
            # We don't have rights, so just kick the bastard
            self.kick(room, jid)

        self.log.warn("Banning '{0}' from room {1}.".format(jid, room))
        query = ET.Element("{http://jabber.org/protocol/muc#admin}query")
        item = ET.Element("item", {"affiliation":"outcast", "jid":jid})
        reason = ET.Element("reason")
        reason.text = "spam"
        item.append(reason)
        query.append(item)
        iq = self.bot.makeIqSet(query)
        iq["to"] = room
        result = iq.send()
        return True


    def shutDown(self):
        self.bot.del_event_handler("groupchat_message", self.checkSpam)
