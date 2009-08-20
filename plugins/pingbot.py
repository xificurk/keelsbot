# This Python file uses the following encoding: utf-8
"""
    pingbot.py - A plugin for pinging Jids.
    Copyright (C) 2007 Kevin Smith
    Translation by Petr Morávek

    KeelsBot is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    KeelsBot is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this software; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import logging

class pingbot(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = u"'Pingbot' umožňuje uživatelům pingnout jiné JIDy.\nAutor: Kevin Smith"
        self.bot.addCommand('ping', self.handle_ping, 'Ping', u"Zobrazuje odezvu k zadanému JIDu.", 'ping jid')

    def handle_ping(self, command, args, msg):
        latency = self.bot['xep_0199'].sendPing(args, 10)
        if latency == None:
            response = u"Žádná odezva od " + args
        else:
            response = u"Odezva od %s obdržena za %d sekund." % (args, latency)
        return response
