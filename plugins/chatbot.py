# -*- coding: utf-8 -*-
"""
chatbot plugin: Bot chats with users.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2008 Pavel Šimerda",
                 "Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import datetime
import glob
import logging
import os.path
import random
import re
import time
from xml.etree import cElementTree as ET

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class chatbot:
    dictionary_files = []
    states_muc = {}
    states_jid = {}
    rooms = {}
    msg_times = {}
    logger = None

    def __init__(self, bot, config):
        self.bot = bot
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext

        self.filters = Filters(bot)

        for muc in config.get("muc", []):
            if "room" not in muc:
                log.error(_("Configuration error - room attribute of muc required."))
                continue
            room = muc["room"]
            if room not in self.bot.muc_nicks:
                log.error(("Bot is not configured to sit in room {}.").format(room))
                continue
            self.states_muc[room] = {}
            if "disabled" in muc:
                log.debug(_("NOT starting to chat in room {}").format(room))
                self.rooms[room] = {"chatty":False, "msg_counter":0}
            else:
                log.debug(_("Starting to chat in room {}").format(room))
                self.rooms[room] = {"chatty":True, "msg_counter":0}

        for dictionary in config.get("dict", []):
            if "path" not in dictionary:
                log.error(_("Configuration error - path attribute of dictionary required."))
                continue
            self.dictionary_files.append(dictionary["path"])
        self.conversations = Conversations(self.dictionary_files)

        log_path = config.get("config", {}).get("log")
        if log_path is not None:
            self.logger = Logger(log_path)

        self.bot.add_command("shut", self.shut, __("Disable chatbot in MUC"), __("Bot stops replying in public chat of given (or current) MUC."), __("[room@server]"))
        self.bot.add_command("chat", self.chat, __("Enable chatbot in MUC"), __("Bot starts replying in public chat of given (or current) MUC."), __("[room@server]"))
        self.bot.add_command("convreload", self.reload, __("Reload conversation files"), __("Reloads conversation files without dropping out of MUC or forgetting current state."))
        self.bot.add_event_handler("message", self.handle_message, threaded=False)

    def shutdown(self, bot):
        bot.del_event_handler("message", self.handle_message)

    def chat(self, command, args, msg, uc):
        if args == "":
            args = msg["from"].bare

        if args in self.rooms:
            self.rooms[args]["chatty"] = True
            return self.gettext("OK, I'll start chatting in room {}.", uc.lang).format(args)
        else:
            return self.gettext("Sorry, I can't chat in room {} at all.", uc.lang).format(args)

    def shut(self, command, args, msg, uc):
        if args == "":
            args = msg["from"].bare

        if args in self.rooms:
            self.rooms[args]["chatty"] = False
            return self.gettext("OK, I'll stop chatting in room {}.", uc.lang).format(args)
        else:
            return self.gettext("Sorry, I don't chat in room {} at all.", uc.lang).format(args)

    def reload(self, command, args, msg, uc):
        self.conversations = Conversations(self.dictionary_files)
        log.info(_("Conversation files reloaded."))
        return self.gettext("OK, I've reloaded conversation files ;-)", uc.lang)

    def handle_message(self, msg):
        """ Handle message for chatbot """
        if msg["type"] not in ("groupchat", "chat"):
            return

        msg_counter = self._response_init(msg)
        if msg_counter is False:
            return

        if msg["type"] == "groupchat":
            message, flags, state, state_others = self._prepare_response_muc(msg, msg_counter)
        else:
            flags = ["chat", "direct", "private"]
            if msg["from"].bare in self.states_muc:
                message, state, state_others = self._prepare_response_muc_pm(msg)
            else:
                message, state = self._prepare_response_pm(msg)
                state_others = []

        log.debug(flags)
        response, state_new, filters = self.conversations.get_response(state, state_others, message, flags)
        if self.logger is not None:
            self.logger.log(msg, response)

        if response is not None:
            if msg["type"] == "groupchat":
                room = msg["mucroom"]
                nick = msg["mucnick"]
                self.states_muc[room][nick]["public"] = {"msg_timer":time.time(), "msg_counter":msg_counter, "state":state_new}
                if "direct" in flags and "direct" not in filters:
                    filters.append("direct")
            elif msg["from"].bare in self.rooms:
                room = msg["from"].bare
                nick = msg["from"].resource
                self.states_muc[room][nick]["private"] = {"msg_timer":time.time(), "state":state_new}
                if "no-direct" not in filters:
                    filters.append("no-direct")
            else:
                self.states_jid[msg["from"].bare] = {"msg_timer":time.time(), "state":state_new}
                if "no-direct" not in filters:
                    filters.append("no-direct")

        if response is not None and response != "":
            prefix, response = self._response_filters(msg, response, filters)
            self._schedule_response(msg, prefix, response)

    def _schedule_response(self, msg, prefix, response):
        if msg["type"] == "groupchat":
            mtype = "groupchat"
            mto = msg["from"].bare
        else:
            mtype = "chat"
            mto = msg["from"].full
        now = time.time()
        for prefix, response in self._parse_multiline(prefix, response):
            wait = random.uniform(min(8, max(1, len(response)/9)), min(25, max(5, len(response)/6))) + max(0, self.msg_times.get(mto, 0) - now)
            self.msg_times[mto] = now + wait
            self.bot.schedule("chatbot_message", wait, self.bot.send_message, (mto, prefix+response, None, mtype))

    def _parse_multiline(self, prefix, response):
        """ Parses | out into multiple strings and actions. """
        lines = []
        for line in response.split("|"):
            if line.startswith("/"):
                lines.append(("", "/me " + line[1:]))
            else:
                lines.append((prefix, line))
        return lines

    def _response_init(self, msg):
        """ Should chatbot respond? Return msg_counter """
        msg_counter = None
        if msg["type"] == "groupchat":
            room = msg["mucroom"]
            if msg["from"].full == room or room not in self.rooms:
                # system message
                return False
            else:
                self.rooms[room]["msg_counter"] += 1
                msg_counter = self.rooms[room]["msg_counter"]

            if self.bot.muc_nicks[room] == msg["mucnick"]:
                # our message
                return False
            if self.rooms[room]["chatty"] == False:
                # shouldn't chat
                return False

        uc = self.bot.get_user_config(msg["from"])
        if uc.level < 0:
            # ignore user
            return False

        message = msg.get("body", "")
        if message.startswith(self.bot.cmd_prefix):
            respond = False
            # Remove cmd_prefix from message
            message = message[len(self.bot.cmd_prefix):]

            # Get command name
            command = message.split("\n", 1)[0].split(" ", 1)[0]
            if len(command) == 0 or command not in self.bot.commands or self.bot.permissions["command:"+command] > uc.level:
                respond = True

            if not respond:
                return False

        return msg_counter

    def _prepare_response_muc(self, msg, msg_counter):
        """ Parse MUC public message """
        message = msg.get("body", "")
        room = msg["mucroom"]
        nick = msg["mucnick"]
        message = message.replace(self.bot.muc_nicks[room], "//BOTNICK//")

        match = re.match("^//BOTNICK//[:,>] ?(.*)$", message)
        if match is not None:
            message = match.group(1)
            flags = ["chat", "direct", "public"]
        else:
            flags = ["chat", "global", "public"]

        states = self.states_muc[room]
        if nick not in states:
            states[nick] = {"private":{}, "public":{}}

        msg_counter_old = states[nick]["public"].get("msg_counter", None)
        msg_timer_old = states[nick]["public"].get("msg_timer", None)
        state = []
        if msg_counter_old is not None and (msg_counter - msg_counter_old) <= 30 and msg_timer_old is not None and (time.time() - msg_timer_old) <= 2*3600:
            state = states[nick]["public"].get("state", [])
        else:
            states[nick]["public"]["state"] = []

        state_others = []
        for name in states:
            if name == nick:
                continue
            msg_counter_old = states[name]["public"].get("msg_counter", None)
            msg_timer_old = states[name]["public"].get("msg_timer", None)
            if msg_counter_old is not None and (msg_counter - msg_counter_old) <= 5 and msg_timer_old is not None and (time.time() - msg_timer_old) <= 1800:
                state_others.extend(states[name]["public"].get("state", []))

        return message, flags, state, state_others

    def _prepare_response_muc_pm(self, msg):
        """ Parse MUC private message """
        message = msg.get("body", "")
        room = msg["from"].bare
        nick = msg["from"].resource

        states = self.states_muc[room]
        if nick not in states:
            states[nick] = {"private":{}, "public":{}}

        msg_timer_old = states[nick]["private"].get("msg_timer", None)
        state = []
        if msg_timer_old is not None and (time.time() - msg_timer_old) <= 2*3600:
            state = states[nick]["private"].get("state", [])
        else:
            states[nick]["private"]["state"] = []

        state_others = []
        msg_timer_old = states[nick]["public"].get("msg_timer", None)
        if msg_timer_old is not None and (time.time() - msg_timer_old) <= 1800:
            state_others.extend(states[nick]["public"].get("state", []))

        return message, state, state_others

    def _prepare_response_pm(self, msg):
        """ Parse private message """
        message = msg.get("body", "")
        jid = msg["from"].bare

        states = self.states_jid
        if jid not in states:
            states[jid] = {}

        msg_timer_old = states[jid].get("msg_timer", None)
        state = []
        if msg_timer_old is not None and (time.time() - msg_timer_old) <= 2*3600:
            state = states[jid].get("state", [])
        else:
            states[jid]["state"] = []

        return message, state

    def _response_filters(self, msg, response, filters):
        """ Apply filters """
        prefix = ""

        for name in filters:
            if not name.startswith("no-") and "no-{}".format(name) not in filters:
                try:
                    filt = getattr(self.filters, name)
                    prefix, response = filt(msg, prefix, response)
                except:
                    log.exception(_("Filter error: {}.").format(name))

        return prefix, response


class Filters:
    def __init__(self, bot):
        self.bot = bot

    def common(self, msg, prefix, response):
        response = response.replace("////", "\n")

        if msg["from"].bare in self.bot.muc_nicks:
            response = response.replace("//BOTNICK//", self.bot.muc_nicks[msg["from"].bare])
            response = response.replace("//NICK//", msg["from"].resource)

        return prefix, response

    def direct(self, msg, prefix, response):
        prefix = ""
        if msg["type"] == "groupchat":
            prefix = "{}: ".format(msg["mucnick"])

        return prefix, response

    def time(self, msg, prefix, response):
        now = datetime.datetime.now()
        return prefix, response.replace("//TIME//", "{:d}:{:02d}".format(now.hour, now.minute))

    def date(self, msg, prefix, response):
        now = datetime.datetime.now()
        return prefix, response.replace("//DATE//", "{}.{}.".format(now.day, now.month))


class Conversations:
    queries = []

    def __init__(self, filenames=[]):
        files = []
        for filename in filenames:
            log.debug(filename)
            files.extend(glob.glob(filename))
        for filename in sorted(files):
            self.load_file(filename)

    def load_file(self, filename):
        log.debug(_("Loading conversation file {}.").format(filename))
        root = ET.parse(filename)
        id_map = {}
        data = {}
        data["queries"] = []
        self._parse_queries(root, data, id_map)
        self._replace_ids(id_map, data["queries"], "replies")
        self.queries.extend(data["queries"])

    def _parse_queries(self, element, context, id_map):
        for query in element.findall("query"):
            try:
                item = dict(query.attrib)
                item["scope"] = item.get("scope", "direct")
                item["pattern"] = re.compile(item.pop("match"),  re.I | re.U)
                item["replies"] = []
                if "id" in item:
                    id_map[item["id"]] = item
                context["queries"].append(item)
                self._parse_replies(query, item, id_map)
            except re.error:
                log.exception(_("Regular expression error: {!r}.").format(query.attrib["match"]))

    def _parse_replies(self, element, context, id_map):
        for reply in element.findall("reply"):
            item = dict(reply.attrib)
            item["text"] = item.get("text", "")
            item["scope"] = item.get("scope", "chat")
            item["weight"] = int(item.get("weight", 1))
            item["queries"] = []
            if "id" in item:
                id_map[item["id"]] = item
            context["replies"].append(item)
            self._parse_queries(reply, item, id_map)

    def _replace_ids(self, id_map, context, element):
        if element == "replies":
            child_element = "queries"
        else:
            child_element = "replies"
        for item in context:
            self._replace_ids(id_map, item[element], child_element)
            if "extends" in item:
                extends = item.pop("extends")
                if extends in id_map:
                    item[element].extend(id_map[extends][element])
                else:
                    log.error(_("Could not find matching element with id {!r}.").format(extends))

    def get_response(self, state, state_others, query, flags=["chat"]):
        log.debug(_("Getting response for {!r}.").format(query))
        queries = []
        queries += filter(lambda i: i["scope"] in flags, state)
        queries += filter(lambda i: i["scope"] in flags, state_others)
        queries += filter(lambda i: i["scope"] in flags, self.queries)
        log.debug(_("Got {} queries left from {}, {}, {}.").format(len(queries), len(state), len(state_others), len(self.queries)))

        for item in queries:
            if item["pattern"].search(query) is not None:
                response = self._get_random_response(item["replies"], flags)
                if response is None:
                    continue

                filters = response.get("filter", "common")
                if filters != "common":
                    filters = "{} common".format(filters)

                log.debug("Got {!r}.".format(response["text"]))
                return response["text"], response["queries"], filters.split(" ")

        return None, None, None

    def _get_random_response(self, choices, flags=["chat"]):
        replies = []
        replies += filter(lambda i: i["scope"] in flags, choices)

        if len(replies) == 0:
            return None
        elif len(replies) == 1:
            return replies[0]

        sum_ = 0
        for item in replies:
            sum_ += item["weight"]

        log.debug(_("Randomly choosing from {} choices (weight sum {}).").format(len(replies), sum_))

        select = random.randint(1, sum_)
        sum_ = 0
        for item in replies:
            sum_ += item["weight"]
            if select <= sum_:
                return item


class Logger:
    def __init__(self, path):
        self.path = path

    def log(self, msg, response):
        message = msg.get("body", "").replace("\n", "||")
        if msg["type"] == "groupchat":
            filename = "{}.log".format(msg["mucroom"])
            message = "{}\t{}".format(msg["mucnick"], message)
        else:
            filename = "{}---{}.log".format(msg["from"].bare.replace("/", "-"), msg["from"].resource.replace("/", "-"))

        dnf = "OK"
        if response is None:
            dnf = "DNF"
        else:
            response = response.replace("\n", "||")

        with open(os.path.join(self.path, filename), "a") as fp:
            fp.write("{:%Y-%m-%d %X}\t{}\t{}\n\t\t{}\n".format(datetime.datetime.now(), dnf, message, response))
