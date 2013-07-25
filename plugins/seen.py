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
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext
        self.store = Storage(bot.store)

        bot.add_command("seen", self.seen, __("User last seen"), __("Display the last sighting of the user in MUC room."), __("nick"))
        bot.add_event_handler("got_online", self.handle_got_online, threaded=True) # Unfortunately we're double-logging a bit here
        bot.add_event_handler("groupchat_presence", self.handle_presence, threaded=True)
        bot.add_event_handler("groupchat_message", self.handle_message, threaded=True)

    def shutdown(self, bot):
        bot.del_event_handler("got_online", self.handle_got_online)
        bot.del_event_handler("groupchat_presence", self.handle_presence)
        bot.del_event_handler("groupchat_message", self.handle_message)

    def handle_got_online(self, pr):
        if "muc" not in pr.keys() or pr["type"] in ("error", "probe"):
            return
        self.store.update(pr["muc"]["room"], pr["muc"]["nick"], "got_online", pr.get("status"))

    def handle_presence(self, pr):
        self.store.update(pr["muc"]["room"], pr["muc"]["nick"], "presence", pr.get("status"))

    def handle_message(self, msg):
        self.store.update(msg["mucroom"], msg["mucnick"], "message", msg.get("body", ""))

    def seen(self, command, args, msg, uc):
        room = msg["from"].bare
        if room not in self.xep_0045.getJoinedRooms():
            return self.gettext("I'm not in room {}, so I can't track users activity there.", uc.lang).format(room)

        if args == "":
            return self.gettext("You have to tell me about whom you want information!", uc.lang)

        roster = self.xep_0045.getRoster(room) or []
        if args in roster:
            seen = self.store.getActivity(room, args)
            if seen is None:
                # We have somehow missed got_online or message of the user.
                return self.gettext("{} idles in the room.", uc.lang).format(args)
            else:
                delta = self.format_timedelta(time.time() - seen[0], uc.lang)
                return self.gettext("{} idles in the room for {}.", uc.lang).format(args, delta)
        else:
            seen = self.store.get(room, args)
            if seen is None:
                return self.gettext("{}? I have no idea about whom you're talking...", uc.lang).format(args)
            else:
                delta = self.format_timedelta(time.time() - seen[0], uc.lang)
                return self.gettext("It's {} since I last saw {} in the room.", uc.lang).format(delta, args)

    def format_timedelta(self, delta, lang):
        parts = []

        months = int(delta/3600/24/30)
        if months > 0:
            delta -= months*3600*24*30
            parts.append(self.ngettext("already {} month", "already {} months", months, lang).split(" ", 1)[1].format(months))

        days = int(delta/3600/24)
        if days > 0 or len(parts) > 0:
            delta -= days*3600*24
            parts.append(self.ngettext("already {} day", "already {} days", days, lang).split(" ", 1)[1].format(days))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        hours = int(delta/3600)
        if hours > 0 or len(parts) > 0:
            delta -= hours*3600
            parts.append(self.ngettext("already {} hour", "already {} hours", hours, lang).split(" ", 1)[1].format(hours))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        minutes = int(delta/60)
        if minutes > 0 or len(parts) > 0:
            delta -= minutes*60
            parts.append(self.ngettext("already {} minute", "already {} minutes", minutes, lang).split(" ", 1)[1].format(minutes))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        seconds = int(delta)
        parts.append(self.ngettext("already {} second", "already {} seconds", seconds, lang).split(" ", 1)[1].format(seconds))
        return self.gettext(" and ", lang).join(parts)


class Storage:
    events = ("message", "got_online", "got_offline", "presence")

    def __init__(self, store):
        self.store = store
        self.create_tables()

    def create_tables(self):
        with self.store.lock:
            self.store.query("""CREATE TABLE IF NOT EXISTS seen (
                            room VARCHAR(256) NOT NULL,
                            nick VARCHAR(256) NOT NULL,
                            event INTEGER(1) NOT NULL,
                            timestamp INT NOT NULL,
                            text VARCHAR(256),
                            PRIMARY KEY (room, nick, event))""")

    def update(self, room, nick, event, text=None):
        event = self.events.index(event)
        log.debug(_("Updating seen record for {!r} in {}.").format(nick, room))
        with self.store.lock:
            self.store.query("INSERT OR REPLACE INTO seen (room, nick, event, timestamp, text) VALUES(?,?,?,?,?)", (room, nick, event, int(time.time()), text))

    def get(self, room, nick):
        with self.store.lock:
            result = self.store.query("SELECT event, timestamp, text FROM seen WHERE room=? AND nick=? ORDER BY timestamp DESC LIMIT 1", (room, nick))
        if len(result) == 0:
            return None
        result = result[0]
        return (int(result["timestamp"]), result["text"], self.events[int(result["event"])])

    def getActivity(self, room, nick):
        with self.store.lock:
            result = self.store.query("SELECT event, timestamp, text FROM seen WHERE room=? AND nick=? AND (event=? OR event=?) ORDER BY timestamp DESC LIMIT 1", (room, nick, self.events.index("message"), self.events.index("got_online")))
        if len(result) == 0:
            return None
        result = result[0]
        return (int(result["timestamp"]), result["text"], self.events[int(result["event"])])
