# -*- coding: utf-8 -*-
"""
    plugins/admin.py - A plugin for administering the bot.
    Copyright (C) 2007 Kevin Smith
    Copyright (C) 2008-2010 Petr Morávek

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

class admin(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = "'Admin' umožňuje vlastníkům bota provádět akce jako restart bota vzdáleně.\nAutoři: Kevin Smith, Petr Morávek"
        self.bot.addCommand("rehash", self.rehash, "Rehash", "Znovu načíst konfiguraci a pluginy bota aniž by se odpojil z jabberu.", "rehash")
        self.bot.addCommand("restart", self.restart, "Restart", "Restartovat bota a znovu připojit...", "restart")
        self.bot.addCommand("die", self.die, "Die", "Killnout bota.", "die")

    def rehash(self, command, args, msg):
        self.bot.rehash()
        return "Rehashnuto, šéfiku."

    def restart(self, command, args, msg):
        self.bot.restart()
        return "Restartováno, šéfiku."

    def die(self, command, args, msg):
        self.bot.die()
        return "Umírám..."
