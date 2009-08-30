# This Python file uses the following encoding: utf-8
"""
    plugins/admin.py - A plugin for administering the bot.
    Copyright (C) 2007 Kevin Smith
    Copyright (C) 2008, 2009 Petr Morávek

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

class admin(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = u"'Admin' umožňuje vlastníkům bota provádět akce jako restart bota vzdáleně.\nAutoři: Kevin Smith, Petr Morávek"
        self.bot.addCommand('rehash', self.handle_rehash, 'Rehash', u"Znovu načíst konfiguraci a pluginy bota aniž by se odpojil z jabberu.", 'rehash')
        self.bot.addCommand('die', self.handle_die, 'Die', u"Killnout bota.", 'die')
        self.bot.addCommand('restart', self.handle_restart, 'Restart', u"Restartovat bota a znovu připojit...", 'restart')

    def handle_rehash(self, command, args, msg):
        self.bot.rehash()
        response = u"Rehashnuto šéfiku."
        return response

    def handle_restart(self, command, args, msg):
        self.bot.restart()
        response = u"Restartováno šéfiku."
        return response

    def handle_die(self, command, args, msg):
        response = u"Umírám..."
        self.bot.die()
        return response
