# -*- coding: utf-8 -*-
"""
    plugins/help.py - A plugin for displaying help for commands and other 
    topics.
    Copyright (C) 2008 Petr Morávek

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

class help(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = "'Help' slouží pro vypisování nápovědy k příkazům KeelsBota.\nAutor: Petr Morávek"
        self.bot.addCommand('help', self.handle_help, "Nápověda", "Pokud nebylo určeno téma, vypíše seznam dostupných příkazů a dalších možných témat nápovědy. V opačném případě vypíše nápovědu na dané téma.", "help [téma/příkaz]")
        self.bot.addCommand('commands', self.handle_commands, "Příkazy", "Vypíše seznam dostupných příkazů.", "commands")

    def handle_commands(self, command, args, msg):
        level = self.bot.getAccessLevel(msg)
        response = "Dostupné příkazy:\n"
        for cmd in sorted(self.bot.commands):
            if self.bot.commands[cmd]["level"] > level:
                continue
            response += self.bot.cmd_prefix + "%s" % (cmd)
            if self.bot.help[cmd][0] is not None:
                response += " -- %s" % (self.bot.help[cmd][0])
            response += "\n"
        return response

    def handle_help(self, command, args, msg):
        response = ''
        if not args:
            response += self.handle_commands(command, args, msg)
            start = True
            for topic in sorted(self.bot.help):
                if topic in self.bot.commands:
                    continue
                if start:
                    response += "\nDalší dostupná témata nápovědy:\n"
                    start = False
                response += "%s" % (topic)
                if self.bot.help[topic][0] is not None:
                    response += " -- %s" % (self.bot.help[topic][0])
                response += "\n"
            args = 'help'
            response += "---------\n"

        if args.startswith(self.bot.cmd_prefix) and len(args) > len(self.bot.cmd_prefix):
            if len(self.bot.cmd_prefix):
                args = args.split(self.bot.cmd_prefix, 1)[-1]

        if args in self.bot.help:
            isCommand = False
            if args in self.bot.commands:
                isCommand = True
                if self.bot.getAccessLevel(msg) < self.bot.commands[args]['level']:
                    return "Neznám, neumím..."
            response += "%s\n" % self.bot.help[args][0]
            response += self.bot.help[args][1]
            if self.bot.help[args][2] and isCommand:
                response += "\n\nPoužití: %s%s" % (self.bot.cmd_prefix, self.bot.help[args][2])
        else:
            response += "Neznám, neumím..."
        return response
