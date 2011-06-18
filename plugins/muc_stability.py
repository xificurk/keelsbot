# -*- coding: utf-8 -*-
"""
muc_stability plugin: Keeps the bot connected to MUC channels.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2008 Kevin Smith",
                 "Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging
import threading
import time
from sleekxmpp.xmlstream.handler.callback import Callback
from sleekxmpp.xmlstream.matcher.stanzapath import StanzaPath

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class muc_stability:
    sleek_plugins = ("xep_0045",)
    _loop_interval = 4
    _check_interval = 600
    run = False

    def __init__(self, bot, config):
        self.bot = bot
        self.lock = threading.RLock()

        bot.register_handler(Callback(
            "keelsbot.muc_stability.handle_error",
            StanzaPath("{{{}}}message@type=error/error@type=modify@code=406@condition=not-acceptable".format(bot.default_ns)),
            self.handle_error))
        bot.add_event_handler("session_start", self.handle_session_start, threaded=True)
        bot.add_event_handler("disconnected", self.handle_disconnected, threaded=True)
        with self.lock:
             if bot.state.ensure("connected") and bot.session_started_event.isSet():
                 # In case we're already connected, start right away
                self.handle_session_start()

    def handle_session_start(self, data=None):
        with self.lock:
            if self.run:
                # Loops are already started
                return
            self.run = True
            thread = threading.Thread(target=self.loop)
            thread.daemon = True
            self.thread = thread
            thread.start()

    def handle_disconnected(self, data=None):
        with self.lock:
            self.run = False
            # Join thread
            self.thread.join()

    def shutdown(self, bot):
        with self.lock:
            bot.remove_handler("keelsbot.muc_stability.handle_error")
            bot.del_event_handler("session_start", self.handle_session_start)
            bot.del_event_handler("disconnected", self.handle_disconnected)
            self.handle_disconnected()

    def handle_error(self, msg):
        """ Check if error message comes from MUC and rejoin. """
        room = msg["from"].bare
        if room not in self.bot.muc_nicks:
            return
        nick = self.bot.muc_nicks[room]
        log.info(_("Rejoining the room {} as {!r}.").format(room, nick))
        self.xep_0045.joinMUC(room, nick)

    def loop(self):
        """ The loop that periodically checks joined MUCs. """
        log.debug(_("Entering the loop."))

        while self.run:
            wait = 0
            while self.run and wait < self._check_interval:
                wait += self._loop_interval
                time.sleep(self._loop_interval)

            if not self.run:
                break

            for room, nick in self.bot.muc_nicks.items():
                if room not in self.xep_0045.getJoinedRooms():
                    log.info(_("Rejoining the room {} as {!r}.").format(room, nick))
                    self.xep_0045.joinMUC(room, nick)
                else:
                    jid = "{}/{}".format(room, nick)
                    self.bot.send_message(jid, None, mtype="chat")

        log.debug(_("Exiting the loop."))
