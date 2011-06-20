# -*- coding: utf-8 -*-
"""
seen plugin: Traks user sightings in MUC.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2007 Kevin Smith",
                 "Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging
import time

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class seen:
    sleek_plugins = ("xep_0045",)

    def __init__(self, bot, config):
        self.bot = bot
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext
        self.store = Storage(bot.store)

        bot.add_command("seen", self.seen, __("Last seen user"), __("Displays the last sighting of the user."), __("nick"))
        bot.add_event_handler("groupchat_presence", self.handle_presence, threaded=True)
        bot.add_event_handler("groupchat_message", self.handle_message, threaded=True)

    def shutdown(self, bot):
        bot.del_event_handler("groupchat_presence", self.handle_presence)
        bot.del_event_handler("groupchat_message", self.handle_message)

    def handle_presence(self, pr):
        """ Keep track of the user's presences. """
        if pr["type"] in ("error", "probe"):
            return
        room = pr["muc"]["room"]
        if pr["muc"]["nick"] in ("", self.bot.muc_nicks.get(room)):
            return
        if pr["type"] == "unavailable":
            event = "leave"
        else:
            event = "presence"
        self.store.update(pr["muc"]["nick"], room, event, pr.get("status"))

    def handle_message(self, msg):
        """ Keep track of user's messages. """
        if msg["type"] in ("error", "headline"):
            return
        room = msg["mucroom"]
        if msg["mucnick"] in ("", self.bot.muc_nicks.get(room)):
            return
        self.store.update(msg["mucnick"], room, "message", msg.get("body", ""))

    def seen(self, command, args, msg, uc):
        if args == "":
            return self.gettext("You have to tell me about whom you want information!", uc.lang)

        if args == self.bot.muc_nicks.get(msg["from"].bare):
            return self.gettext("I'm right HERE, you moron! ;-)", uc.lang)

        seen = self.store.get(args)
        if seen == None:
            return self.gettext("{}? I have no idea about whom you're talking...", uc.lang).format(args)

        delta = self.format_timedelta(time.time() - seen[0], uc.lang)

        status = ""
        if seen[2] == "message":
            status = self.gettext(" writing \"{}\"", uc.lang).format(seen[3] or "")
        elif seen[3] is not None:
            status = " ({})".format(seen[3])

        if seen[2] == "leave":
            state = self.gettext(" leaving room", uc.lang)
        else:
            state = self.gettext(" in room", uc.lang)

        return self.gettext("It's {} since {} was seen{} {}{}.", uc.lang).format(delta, args, state, seen[1], status)

    def format_timedelta(self, delta, lang):
        parts = []

        months = int(delta/3600/24/30)
        if months > 0:
            delta -= months*3600*24*30
            parts.append(self.ngettext("{} month", "{} months", months, lang).format(months))

        days = int(delta/3600/24)
        if days > 0 or len(parts) > 0:
            delta -= days*3600*24
            parts.append(self.ngettext("{} day", "{} days", days, lang).format(days))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        hours = int(delta/3600)
        if hours > 0 or len(parts) > 0:
            delta -= hours*3600
            parts.append(self.ngettext("{} hour", "{} hours", hours, lang).format(hours))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        minutes = int(delta/60)
        if minutes > 0 or len(parts) > 0:
            delta -= minutes*60
            parts.append(self.ngettext("{} minute", "{} minutes", minutes, lang).format(minutes))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        seconds = int(delta)
        parts.append(self.ngettext("{} second", "{} seconds", seconds, lang).format(seconds))
        return self.gettext(" and ", lang).join(parts)


class Storage:
    events = ("message", "presence", "leave")

    def __init__(self, store):
        self.store = store
        self.create_tables()

    def create_tables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS seen (
                            nick VARCHAR(256) NOT NULL PRIMARY KEY,
                            room VARCHAR(256) NOT NULL,
                            event INTEGER(1) NOT NULL,
                            timestamp INT NOT NULL,
                            text VARCHAR(256))""")

    def update(self, nick, room, event, text=None):
        if event not in self.events:
            raise ValueError
        else:
            event = self.events.index(event)
        log.debug(_("Updating seen record for {!r}.").format(nick))
        self.store.query("INSERT OR REPLACE INTO seen (nick, room, event, timestamp, text) VALUES(?,?,?,?,?)", (nick, room, event, int(time.time()), text))

    def get(self, nick):
        result = self.store.query("SELECT * FROM seen WHERE nick=?", (nick,))
        if len(result) == 0:
            return None
        result = result[0]
        return (int(result["timestamp"]), result["room"], self.events[int(result["event"])], result["text"])
