# -*- coding: utf-8 -*-
"""
twitter plugin: Expands twitter status links.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging
import re
from twython3k import Twython

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class twitter:
    rooms = []

    def __init__(self, bot, config):
        self.bot = bot
        self.twython = Twython()
        for muc in config["muc"]:
            room = muc.get("room")
            if room is None:
                log.error(_("Configuration error - room attribute of muc required."))
                continue
            bot.add_event_handler("muc::{}::message".format(room), self.handle_message, threaded=True)

    def shutdown(self, bot):
        for room in self.rooms:
            bot.del_event_handler("muc::{}::message".format(room), self.handle_message)

    def handle_message(self, msg):
        match = re.search("https?://twitter\.com/#!/.*?/status/([0-9]+)", msg.get("body"))
        if match is None:
            return
        status_id = match.group(1)
        try:
            status = self.twython.showStatus(id=status_id)
            name = status["user"]["screen_name"]
            status = status["text"]
        except:
            log.debug(_("Got error while getting twitter status {}.").format(status_id))
            return
        self.bot.send_message(msg["mucroom"], "@{}: {}".format(name, status), mtype="groupchat")
