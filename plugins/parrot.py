# -*- coding: utf-8 -*-
"""
parrot plugin: Sends out messages to MUC or JID.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2007 Kevin Smith",
                 "Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class parrot:
    def __init__(self, bot, config):
        self.bot = bot
        self.gettext = self.bot.gettext
        self.ngettext = self.bot.ngettext

        bot.add_command("say", self.say, __("Send message into MUC"), __("Bot sends the groupchat message into the specified MUC."), __("room@server text"))
        bot.add_command("tell", self.tell, __("Send message to JID"), __("Bot sends the message to the specified JID."), __("user@server text"))

    def say(self, command, args, msg, uc):
        if args.count(" ") >= 1:
            muc, text = args.split(" ", 1)
        else:
            return self.gettext("You've forgot to specify the MUC.", uc.lang)
        if "xep_0045" not in self.bot.plugin or muc not in self.bot.plugin["xep_0045"].getJoinedRooms():
            return self.gettext("I'm not in the room {}.", uc.lang).format(muc)
        self.bot.send_message(muc, text, mtype="groupchat")
        return self.gettext("Sent", uc.lang)

    def tell(self, command, args, msg, uc):
        if args.count(" ") >= 1:
            jid, text = args.split(" ", 1)
        else:
            return self.gettext("You've forgot to specify the JID.", uc.lang)
        self.bot.send_message(jid, text, mtype="chat")
        return self.gettext("Sent", uc.lang)
