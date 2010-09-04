# -*- coding: utf-8 -*-
"""
    plugins/irssilogs.py - A plugin for logging MUC traffice in an irssi style.
    Copyright (C) 2008 Kevin Smith
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
import locale
import logging
import re

from sleekxmpp.xmlstream.handler.callback import Callback
from sleekxmpp.xmlstream.matcher.xmlmask import MatchXMLMask

locale.setlocale(locale.LC_ALL, ("cs_CZ", "UTF-8"))


class irssilogs(object):
    sleekDependencies = ["xep_0045"]

    def __init__(self, bot, config):
        self.log = logging.getLogger("keelsbot.irssilogs")
        self.bot = bot
        self.config = config
        self.about = "'Irssilogs' slouží pro logování dění v MUCu.\nAutoři: Kevin Smith, Petr Morávek"
        self.bot.add_event_handler("groupchat_presence", self.logPresence, threaded=True)
        self.bot.add_event_handler("groupchat_message", self.logMessage, threaded=True)
        self.bot.registerHandler(Callback("keelsbot.irssilogs.subject", MatchXMLMask("<message xmlns='jabber:client' type='groupchat'><subject/></message>"), self.logTopic))
        self.lastdate = datetime.datetime.now()
        self.roomLogFiles = {}
        self.roomMembers = {}
        logs = self.config.findall("log")
        if logs:
            for log in logs:
                room = log.attrib["room"]
                fileName = log.attrib["file"]
                self.roomLogFiles[room] = irssilogfile(fileName)
                self.roomMembers[room] = []
                self.log.debug("Starting logging {0} to {1}.".format(room, fileName))


    def checkDateChange(self, date):
        if date.day != self.lastdate.day:
            self.lastdate = date
            for log in self.roomLogFiles.values():
                log.logDateChange(date)


    def logPresence(self, event):
        """ Monitor MUC presences.
        """
        presence = {}
        presence["dateTime"] = datetime.datetime.now()
        presence["room"] = event["muc"].getRoom()
        presence["nick"] = event["muc"].getNick()
        presence["status"] = event["status"]
        presence["type"] = event["type"]
        self.checkDateChange(presence["dateTime"])

        if presence["room"] in self.roomLogFiles:
            if presence["type"] == "unavailable" or presence["nick"] not in self.roomMembers[presence["room"]]:
                self.roomLogFiles[presence["room"]].logPresence(presence)

                if presence["type"] == "unavailable":
                    if presence["nick"] in self.roomMembers[presence["room"]]:
                        self.roomMembers[presence["room"]].remove(presence["nick"])
                else:
                    self.roomMembers[presence["room"]].append(presence["nick"])


    def logMessage(self, event):
        """ Monitor MUC messages.
        """
        message = {}
        message["dateTime"] = datetime.datetime.now()
        self.checkDateChange(message["dateTime"])

        if event["mucroom"] in self.roomLogFiles:
            message["room"] = event["mucroom"]
            message["message"] = event["body"]

            if event["from"].full == event["mucroom"]:
                # system message
                message["nick"] = ""
            else:
                message["nick"] = event["mucnick"]

            if event["subject"] != "":
                message["subject"] = event["subject"]
                match = re.match("^(.*?) has set the subject to:", message["message"])
                if match is not None:
                    message["nick"] = match.group(1)

            self.roomLogFiles[message["room"]].logMessage(message)


    def logTopic(self, event):
        """ Handle a message event without body element in a muc.
        """
        if event["body"] != "":
            return

        message = {}
        message["dateTime"] = datetime.datetime.now()
        self.checkDateChange(message["dateTime"])

        if event["mucroom"] in self.roomLogFiles:
            message["room"] = event["mucroom"]
            message["message"] = ""
            message["nick"] = event["mucnick"]
            message["subject"] = event["subject"]
            self.roomLogFiles[message["room"]].logMessage(message)


    def shutDown(self):
        self.bot.del_event_handler("groupchat_presence", self.logPresence)
        self.bot.del_event_handler("groupchat_message", self.logMessage)
        self.bot.removeHandler("keelsbot.irssilogs.subject")



class irssilogfile(object):
    """ Handle writing to a single irssi log file.
    """
    def __init__(self, fileName):
        """ Create a logfile handler for a given muc and file.
        """
        self.log = logging.getLogger("keelsbot.irssilogs.file")
        self.logfile = open(fileName, "a")
        self.appendLogLine("--- Začátek logování")
        self.logDateChange(datetime.datetime.now())


    def appendLogLine(self, message):
        """ Append the line to the log.
        """
        self.logfile.write(message + "\n")
        self.logfile.flush()


    def logDateChange(self, date):
        """ Log a date change.
            Format:
            --- Čtvrtek 16.8.2007
        """
        self.appendLogLine(date.strftime("--- %A %x"))


    def logPresence(self, presence):
        """ Log the presence to the file.
            Formats:
            join = "20:06:07 -!- Nick vstoupil"
            quit = "19:07:08 -!- Nick odešel [status]"
        """
        self.log.debug("Logging presence: {0}.".format(presence))
        presence["dateTime"] = presence["dateTime"].strftime("%X")
        if presence["type"] == "unavailable":
            line = "{dateTime} -!- {nick} odešel [{status}]"
        else:
            line = "{dateTime} -!- {nick} vstoupil"
        self.appendLogLine(line.format(**presence))


    def logMessage(self, message):
        """ Log the message to the file.
            Formats:
            message = "09:43:42 <Nick> messagebody"
            action  = "10:45:42  * Nick actionbodies"
            topic   = "18:38:42 -!- Nick nastavil téma na: Nové téma"
        """
        self.log.debug("Logging message: {0}.".format(message))
        message["dateTime"] = message["dateTime"].strftime("%X")
        action = False
        topic = False
        system = False
        if message["message"][:4] == "/me ":
            action = True
            message["message"] = message["message"][4:]
        if message["nick"] == "":
            system = True
        if "subject" in message:
            topic = True

        if topic:
            line = "{dateTime} -!- {nick} nastavil téma na: {subject}"
        elif system:
            line = "{dateTime} -!- {message}"
        elif action:
            line = "{dateTime}  * {nick} {message}"
        else:
            line = "{dateTime} <{nick}> {message}"

        self.appendLogLine(line.format(**message))
