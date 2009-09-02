# -*- coding: utf-8 -*-
"""
    plugins/parrot.py - A plugin for making a bot parrot text to MUC or JID.
    Copyright (C) 2007 Kevin Smith
    Copyright (C) 2009 Petr Morávek

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

import logging
import datetime, time

class parrot(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = u"'Parrot' umožňuje zaslat vybraným uživatelům text jménem bota do MUCu nebo přímo na JID.\nAutoři: Kevin Smith, Petr Morávek"

        self.bot.addCommand(u'say', self.handle_say, u"Zaslat zprávu do MUCu", u"Bot odešle zprávu do zadaného MUCu.", u'say muc text')
        self.bot.addCommand(u'tell', self.handle_tell, u"Zaslat zprávu JID", u"Bot odešle zprávu zadanému JID.", u'tell jid text')

    def handle_say(self, command, args, msg):
        if args.count(" ") >= 1:
            [muc, text] = args.split(" ",1)
        else:
            return u"Nedostatečný počet parametrů."
        self.bot.sendMessage(muc, text, mtype='groupchat')
        return u"Odesláno."

    def handle_tell(self, command, args, msg):
        if args.count(" ") >= 1:
            [jid, text] = args.split(" ",1)
        else:
            return u"Nedostatečný počet parametrů."
        self.bot.sendMessage(jid, text, mtype='chat')
        return u"Odesláno."
