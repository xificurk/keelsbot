# -*- coding: utf-8 -*-
"""
twitter plugin: Expands twitter status links.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


from html.parser import HTMLParser
import logging
import re
from twython import Twython

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class twitter:
    _unescape = HTMLParser().unescape
    rooms = []

    def __init__(self, bot, config):
        self.get_our_nick = bot.get_our_nick

        auth = config.get("auth", {})

        self.twython = Twython(auth.get("app_key"), access_token=auth.get("access_token"))

        for muc in config.get("muc", []):
            room = muc.get("room")
            if room is None:
                log.error(_("Configuration error - room attribute of muc required."))
                continue
            self.rooms.append(room)
            bot.add_event_handler("muc::{}::message".format(room), self.handle_message, threaded=True)

    def shutdown(self, bot):
        for room in self.rooms:
            bot.del_event_handler("muc::{}::message".format(room), self.handle_message)

    def handle_message(self, msg):
        if msg["mucnick"] in ("", self.get_our_nick(msg["mucroom"])):
            # Ignore system and own message in MUC
            return

        match = re.search("https?://(mobile\.)?twitter\.com/.*?/status/([0-9]+)", msg.get("body"))
        if match is None:
            # No twitter status
            return

        status_id = match.group(2)
        try:
            status = self.twython.showStatus(id=status_id)
            name = self._unescape(status["user"]["screen_name"])
            status = self._unescape(status["text"])
        except:
            log.exception(_("Unexpected error while getting twitter status {}.").format(status_id))
            return
        msg.reply("@{}: {}".format(name, status)).send()
