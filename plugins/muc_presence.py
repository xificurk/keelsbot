# -*- coding: utf-8 -*-
"""
muc_presence plugin: Traks number of users in MUC.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import datetime
import logging
import threading
import time

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class muc_presence:
    sleek_plugins = ("xep_0045",)

    def __init__(self, bot, config):
        self.bot = bot
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext
        self.store = Storage(bot.store)
        self.lock = threading.Lock()

        bot.add_command("cu", self.current, __("Current number of users in room"), __("Display current number of users in MUC room."))
        bot.add_command("mu", self.maximum, __("Highest number of users in room"), __("Display historically highest number of users in MUC room."))
        bot.add_event_handler("got_online", self.handle_presence, threaded=True)

    def shutdown(self, bot):
        bot.del_event_handler("got_online", self.handle_presence)

    def handle_presence(self, pr):
        """ Keep track of users in MUC rooms. """
        if "muc" not in pr.keys():
            return
        room = pr["muc"]["room"]
        current = len(self.xep_0045.getRoster(room))
        time.sleep(2)
        with self.lock:
            current = max(len(self.xep_0045.getRoster(room)), current)
            stored = self.store.get(room)
            if stored is None or current > stored[1]:
                self.store.update(room, current)
                self.bot.send_message(room, self.gettext("There is historically highest number of users in the room ({}).", self.bot.users[None].lang).format(current), mtype="groupchat")

    def current(self, command, args, msg, uc):
        room = msg["from"].bare
        if room not in self.xep_0045.getJoinedRooms():
            return

        current = len(self.xep_0045.getRoster(room))
        return self.ngettext("There is currently {} user present in the room.", "There are currently {} users present in the room.", current, uc.lang).format(current)

    def maximum(self, command, args, msg, uc):
        room = msg["from"].bare
        if room not in self.xep_0045.getJoinedRooms():
            return

        stored = self.store.get(room)
        if stored is None:
            return
        dt = datetime.datetime.fromtimestamp(stored[0])
        return self.ngettext("Historically highest number of users was recorded {:%m/%d/%y (%H:%M)}, {} user was present.", "Historically highest number of users was recorded at {:%m/%d/%y (%H:%M)}, {} users were present.", stored[1], uc.lang).format(dt, stored[1])


class Storage:
    def __init__(self, store):
        self.store = store
        self.create_tables()

    def create_tables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS muc_presence (
                            room VARCHAR(256) NOT NULL PRIMARY KEY,
                            users INTEGER(3) NOT NULL,
                            timestamp INT NOT NULL)""")

    def update(self, room, users):
        log.debug(_("Updating muc_presence record for {}.").format(room))
        self.store.query("INSERT OR REPLACE INTO muc_presence (room, users, timestamp) VALUES(?,?,?)", (room, users, int(time.time())))

    def get(self, room):
        result = self.store.query("SELECT * FROM muc_presence WHERE room=? LIMIT 1", (room,))
        if len(result) == 0:
            return None
        result = result[0]
        return (int(result["timestamp"]), result["users"])
