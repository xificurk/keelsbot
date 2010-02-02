# -*- coding: utf-8 -*-
"""
    plugins/chatbot.py - A plugin making a bot chat with users.
    Copyright (C) 2008 Pavel Šimerda
    Copyright (C) 2009-2010 Petr Morávek
    Part of the code was taken from Pavel Šimerda's Arabicus bot under
    CC-attribution license.

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
import glob
import logging
import os.path
import random
import re
import threading
import time
from xml.etree import cElementTree as ET


class chatbot(object):
    def __init__(self, bot, config):
        self.log = logging.getLogger("keelsbot.chatbot")
        self.bot = bot
        self.config = config
        self.statesMUC = {}
        self.statesJID = {}
        self.messageBuffer = []
        self.rooms = {}
        self.filters = Filters(self)

        rooms = config.findall("muc")
        for element in rooms:
            room = element.get("room")
            self.statesMUC[room] = {}
            if element.get("disabled") is None:
                self.log.debug("Starting to chat in room {0}".format(room))
                self.rooms[room] = {"chatty":True, "msgcounter":0}
            else:
                self.log.debug("NOT Starting to chat in room {0}".format(room))
                self.rooms[room] = {"chatty":False, "msgcounter":0}

        self.dicts = []
        dicts = self.config.findall("dict")
        for dict in dicts:
            dict = dict.get("name")
            if dict is not None:
                self.dicts.append(dict)
        self.conversations = Conversations(self.dicts)

        self.logPath = config.get("log")

        self.about = "'Chatbot' umožňuje botovi odpovídat na určité zprávy v MUC i PM.\nAutoři: Pavel Šimerda, Petr Morávek"
        self.bot.addCommand("shut", self.shut, "Vypnout chatbota v MUC", "Bot přestane odpovídat předdefinovanými odpověďmi v zadaném MUC.", "shut [MUC]")
        self.bot.addCommand("chat", self.chat, "Zapnout chatbota v MUC", "Bot začne odpovídat předdefinovanými odpověďmi v zadaném MUC.", "chat [MUC]")
        self.bot.addCommand("convreload", self.reload, "Znovunačtení konverzací", "Bot znovu naparsuje XMLka s uloženými konverzacemi, aniž by při tom opustil jabber, nebo zapomněl současný stav konverzací.", "convreload")
        self.bot.add_event_handler("message", self.message, threaded=True)
        self.running = True
        threading.Thread(target=self.sender).start()


    def sender(self):
        while self.running:
            while len(self.messageBuffer) > 0:
                message = self.messageBuffer.pop(0)
                self.sendResponse(message)
            time.sleep(2)


    def sendResponse(self, msg):
        """ Sends response to the room.
        """
        prefix = msg.get("prefix", "")
        for responseLine in self.parseMultiline(msg["message"], prefix):
            time.sleep(random.randint(min(9, max(2, int(len(responseLine["reply"])/9))), min(25, max(5, int(len(responseLine["reply"])/6)))))
            self.bot.sendMessage(msg["target"], "{prefix}{reply}".format(**responseLine), mtype=msg["type"])


    def parseMultiline(self, response, prefix=""):
        """ Parses | out into multiple strings and actions.
        """
        responses = response.split("|")
        for i in range(len(responses)):
            if responses[i].startswith("/"):
                responses[i] = {"prefix":"", "reply":"/me " + responses[i][1:]}
            else:
                responses[i] = {"prefix":prefix, "reply":responses[i]}
        return responses


    def shutDown(self):
        self.running = False
        self.bot.del_event_handler("message", self.message, threaded=True)


    def chat(self, command, args, msg):
        if args == "":
            args = msg["from"].bare

        if args in self.rooms:
            self.rooms[args]["chatty"] = True
            return "OK, začnu se vykecávat v místnosti {0}.".format(args)
        else:
            return "V místnosti {0} já vůbec nechatuju ;-)".format(args)


    def shut(self, command, args, msg):
        if args == "":
            args = msg["from"].bare

        if args in self.rooms:
            self.rooms[args]["chatty"] = False
            return "OK, v místnosti {0} se už nebudu vykecávat ;-)".format(args)
        else:
            return "V místnosti {0} já vůbec nechatuju ;-)".format(args)


    def reload(self, command, args, msg):
        self.conversations = Conversations(self.dicts)
        self.log.info("Conversation files reloaded.")
        return "Tak jsem to znova načetl, šéfiku."


    def message(self, msg):
        """ Handle message for chatbot
        """
        if msg["type"] not in ("groupchat", "chat"):
            return

        msgCounter = self.responseInit(msg)
        if msgCounter == False:
            return

        if msg["type"] == "groupchat":
            message, flags, convstate, convstateSup = self.responsePrepareMUC(msg, msgCounter)
        else:
            flags = ["chat", "direct", "private"]
            if msg["from"].bare in self.statesMUC:
                message, convstate, convstateSup = self.responsePrepareMUCPM(msg)
            else:
                message, convstate = self.responsePreparePM(msg)
                convstateSup = []

        reply, convstateNew, filters = self.conversations.getReply(convstate, convstateSup, message, flags)

        self.responseLog(msg, reply)

        if reply is not None:
            if msg["type"] == "groupchat":
                room = msg["mucroom"]
                nick = msg["mucnick"]
                self.statesMUC[room][nick]["public"] = {"msgTimer":int(time.time()), "msgCounter":msgCounter, "state":convstateNew}
                if "direct" in flags:
                    filters.extend(["direct"])
            elif msg["from"].bare in self.rooms:
                room = msg["from"].bare
                nick = msg["from"].resource
                self.statesMUC[room][nick]["private"] = {"msgTimer":int(time.time()), "state":convstateNew}
                filters.extend(["no-direct"])
            else:
                self.statesJID[msg["from"].bare] = {"msgTimer":int(time.time()), "state":convstateNew}
                filters.extend(["no-direct"])

        if reply is not None and reply != "":
            prefix, reply = self.responseFilters(msg, reply, filters)

            if msg["type"] == "groupchat":
                msgType = "groupchat"
                msgTarget = msg["from"].bare
            else:
                msgType = "chat"
                msgTarget = msg["from"].full

            self.messageBuffer.append({"message":reply, "prefix":prefix, "type":msgType, "target":msgTarget})


    def responseInit(self, msg):
        """ Should chatbot respond? Return msgCounter
        """
        msgCounter = None
        if msg["type"] == "groupchat":
            room = msg["mucroom"]
            if msg["from"].full == room or room not in self.rooms:
                # system message
                return False
            else:
                self.rooms[room]["msgcounter"] = self.rooms[room]["msgcounter"]+1
                msgCounter = self.rooms[room]["msgcounter"]

            if self.bot.rooms[room] == msg["mucnick"]:
                # our message
                return False
            if self.rooms[room]["chatty"] == False:
                # shouldn't chat
                return False

        level = self.bot.getAccessLevel(msg)
        if level < 0:
            # ignore user
            return False

        message = msg.get("body", "")
        if message.startswith(self.bot.cmdPrefix):
            respond = False
            # Remove cmdPrefix from message
            message = message[len(self.bot.cmdPrefix):]

            if level < self.bot.minAccessLevel:
                respond = True
            else:
                # Get command name
                command = message.split("\n", 1)[0].split(" ", 1)[0]
                if len(command) == 0 or command not in self.bot.commands or self.bot.commands[command]["level"] > level:
                    respond = True

            if not respond:
                return False

        return msgCounter


    def responsePrepareMUC(self, msg, msgCounter):
        """ Parse MUC public message
        """
        flags = []
        message = msg.get("body", "")
        room = msg["from"].bare
        nick = msg["mucnick"]
        message = message.replace(self.bot.rooms[room], "//BOTNICK//")

        match = re.match("^//BOTNICK//[:,>] ?(.*)$", message)
        if match:
            message = match.group(1)
            flags = ["chat", "direct", "public"]
        else:
            flags = ["chat", "global", "public"]

        roomStates = self.statesMUC[room]
        if nick not in roomStates:
            roomStates[nick] = {"private":{}, "public":{}}

        msgCounterOld = roomStates[nick]["public"].get("msgCounter", None)
        msgTimerOld = roomStates[nick]["public"].get("msgTimer", None)
        convstate = []
        if msgCounterOld is not None and (msgCounter - msgCounterOld) <= 30 and msgTimerOld is not None and (int(time.time()) - msgTimerOld) <= 2*3600:
            convstate = roomStates[nick]["public"].get("state", [])
        else:
            roomStates[nick]["public"]["state"] = []

        convstateSup = []
        for name in roomStates:
            if name == nick:
                continue
            msgCounterOld = roomStates[name]["public"].get("msgCounter", None)
            msgTimerOld = roomStates[name]["public"].get("msgTimer", None)
            if msgCounterOld is not None and (msgCounter - msgCounterOld) <= 5 and msgTimerOld is not None and (int(time.time()) - msgTimerOld) <= 1800:
                convstateSup.extend(roomStates[name]["public"].get("state", []))

        return message, flags, convstate, convstateSup


    def responsePrepareMUCPM(self, msg):
        """ Parse MUC private message
        """
        message = msg.get("body", "")
        room = msg["from"].bare
        nick = msg["from"].resource

        roomStates = self.statesMUC[room]
        if nick not in roomStates:
            roomStates[nick] = {"private":{}, "public":{}}

        msgTimerOld = roomStates[nick]["private"].get("msgTimer", None)
        convstate = []
        if msgTimerOld is not None and (int(time.time()) - msgTimerOld) <= 2*3600:
            convstate = roomStates[nick]["private"].get("state", [])
        else:
            roomStates[nick]["private"]["state"] = []

        convstateSup = []
        msgTimerOld = roomStates[nick]["public"].get("msgTimer", None)
        if msgTimerOld is not None and (int(time.time()) - msgTimerOld) <= 1800:
            convstateSup.extend(roomStates[nick]["public"].get("state", []))

        return message, convstate, convstateSup


    def responsePreparePM(self, msg):
        """ Parse private message
        """
        message = msg.get("body", "")
        jid = msg["from"].bare

        statesJID = self.statesJID
        if jid not in statesJID:
            statesJID[jid] = {}

        msgTimerOld = statesJID[jid].get("msgTimer", None)
        convstate = []
        if msgTimerOld is not None and (int(time.time()) - msgTimerOld) <= 2*3600:
            convstate = statesJID[jid].get("state", [])
        else:
            statesJID[jid]["state"] = []

        return message, convstate


    def responseLog(self, msg, reply):
        """ Log response
        """
        if self.logPath is None:
            return

        message = msg.get("body", "")
        if msg["type"] == "groupchat":
            logFile = "{0}.log".format(msg["mucroom"])
            message = "{0}\t{1}".format(msg["mucnick"], message)
        else:
            logFile = "{0}---{1}.log".format(msg["from"].bare.replace("/", "-"), msg["from"].resource.replace("/", "-"))

        dnf = "OK"
        if reply is None:
            dnf = "DNF"
        else:
            reply = reply.replace("\n", "||")

        line = "{0}\t{1}\t{2}\n\t\t{3}\n".format(datetime.datetime.now(), dnf, message.replace("\n", "||"), reply)

        with open(os.path.join(self.logPath, logFile), "a") as fp:
            fp.write(line)


    def responseFilters(self, msg, reply, filters):
        """ Apply filters
        """
        prefix = ""

        for name in filters:
            if not name.startswith("no-") and "no-{0}".format(name) not in filters:
                try:
                    filt = getattr(self.filters, name)
                    prefix, reply = filt(msg, prefix, reply)
                except:
                    self.log.error("Filter error: {0}.".format(name))

        return prefix, reply



class Filters(object):
    def __init__(self, bot):
        self.bot = bot

    def common(self, msg, prefix, reply):
        reply = reply.replace("////", "\n")

        if msg["from"].bare in self.bot.rooms:
            reply = reply.replace("//BOTNICK//", self.bot.bot.rooms[msg["from"].bare])
            reply = reply.replace("//NICK//", msg["from"].resource)

        return prefix, reply


    def direct(self, msg, prefix, reply):
        prefix = ""
        if msg["type"] == "groupchat":
            prefix = "{0}: ".format(msg["mucnick"])

        return prefix, reply


    def time(self, msg, prefix, reply):
        now = datetime.datetime.now()
        return prefix, reply.replace("//TIME//", "{0:d}:{1:02d}".format(now.hour, now.minute))


    def date(self, msg, prefix, reply):
        now = datetime.datetime.now()
        return prefix, reply.replace("//DATE//", "{0}. {1}.".format(now.day, now.month))



class Conversations(object):
    def __init__(self, filenames=[]):
        self.log = logging.getLogger("keelsbot.chatbot.conv")
        self.files = []
        self.queries = []
        for filename in filenames:
            self.files.extend(glob.glob(filename))
        for file in sorted(self.files):
            self.load(file)


    def load(self, file):
        self.log.debug("Loading conversation file {0}.".format(file))
        root = ET.parse(file)

        idMap = {}
        data = {}
        data["queries"] = []
        self.parseQueries(root, data, idMap)
        self.replaceIds(idMap, data["queries"], "replies")
        self.queries.extend(data["queries"])


    def parseQueries(self, element, context, idMap):
        for query in element.findall("query"):
            try:
                item = dict(query.attrib)
                item["scope"] = item.get("scope", "direct")
                item["pattern"] = re.compile(item.pop("match"),  re.I | re.U)
                item["replies"] = []
                if "id" in item:
                    idMap[item["id"]] = item
                context["queries"].append(item)
                self.parseReplies(query, item, idMap)
            except re.error:
                self.log.error("Regular expression error: {0}.".format(repr(query.attrib["match"])))


    def parseReplies(self, element, context, idMap):
        for reply in element.findall("reply"):
            item = dict(reply.attrib)
            item["text"] = item.get("text", "")
            item["scope"] = item.get("scope", "chat")
            item["weight"] = int(item.get("weight", 1))
            item["queries"] = []
            if "id" in item:
                idMap[item["id"]] = item
            context["replies"].append(item)
            self.parseQueries(reply, item, idMap)


    def replaceIds(self, idMap, context, element):
        for item in context:
            if element == "replies":
                next = "queries"
            else:
                next = "replies"
            self.replaceIds(idMap, item[element], next)
            if "extends" in item and item["extends"] in idMap:
                item[element].extend(idMap[item["extends"]][element])
                item.pop("extends")


    def getReply(self, convstate, convstateSup, query, flags=["chat"]):
        self.log.debug("Getting reply for '{0}'.".format(query))
        queries = []
        queries += filter(lambda i: i["scope"] in flags, convstate)
        queries += filter(lambda i: i["scope"] in flags, convstateSup)
        queries += filter(lambda i: i["scope"] in flags, self.queries)

        for item in queries:
            if item["pattern"].search(query) is not None:
                reply = self.getRandomReply(item["replies"], flags)
                if reply is None:
                    continue

                filters = reply.get("filter", "common")
                if filters != "common":
                    filters = "{0} common".format(filters)

                self.log.debug("Got '{0}'.".format(reply["text"]))
                return reply["text"], reply["queries"], filters.split(" ")

        return None, None, None


    def getRandomReply(self, choice, flags=["chat"]):
        replies = []
        replies += filter(lambda i: i["scope"] in flags, choice)

        if len(replies) == 0:
            return None
        elif len(replies) == 1:
            return replies[0]

        sum = 0
        for item in replies:
            sum = sum + item["weight"]

        self.log.debug("Randomly choosing from {0} choices (weight sum {1}).".format(len(replies), sum))

        select = random.randint(1, sum)
        sum = 0
        for item in replies:
            sum = sum + item["weight"]
            if select <= sum:
                return item
