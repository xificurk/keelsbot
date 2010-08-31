# -*- coding: utf-8 -*-
"""
    plugins/parrot.py - A plugin for making a bot parrot text to MUC or JID.
    Copyright (C) 2007 Kevin Smith
    Copyright (C) 2009-2010 Petr Morávek

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


class parrot(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.about = "'Parrot' umožňuje zaslat vybraným uživatelům text jménem bota do MUCu nebo přímo na JID.\nAutoři: Kevin Smith, Petr Morávek"
        bot.addCommand("say", self.say, "Zaslat zprávu do MUCu", "Bot odešle zprávu do zadaného MUCu.", "say muc text")
        bot.addCommand("tell", self.tell, "Zaslat zprávu JID", "Bot odešle zprávu zadanému JID.", "tell jid text")


    def say(self, command, args, msg):
        if args.count(" ") >= 1:
            muc, text = args.split(" ", 1)
        else:
            return "Nedostatečný počet argumentů."
        if muc not in self.bot.rooms:
            return "Tam já nesedím..."
        self.bot.sendMessage(muc, text, mtype="groupchat")
        return "Odesláno."


    def tell(self, command, args, msg):
        if args.count(" ") >= 1:
            jid, text = args.split(" ", 1)
        else:
            return "Nedostatečný počet argumentů."
        self.bot.sendMessage(jid, text, mtype="chat")
        return "Odesláno."
