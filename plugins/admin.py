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

import logging


class admin(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.loglevels = {"ALL":0, "DEBUG":10, "INFO":20, "WARNING":30, "ERROR":40, "CRITICAL":50}
        self.about = "'Admin' umožňuje administrátorům bota provádět akce jako restart bota vzdáleně.\nAutoři: Kevin Smith, Petr Morávek"
        bot.addCommand("rehash", self.rehash, "Rehash", "Znovu načíst konfiguraci a pluginy bota aniž by se odpojil z jabberu.", "rehash")
        bot.addCommand("restart", self.restart, "Restart", "Restartovat bota a znovu připojit...", "restart")
        bot.addCommand("die", self.die, "Die", "Killnout bota.", "die")
        bot.addCommand("loglevel", self.loglevel, "Log level", "Nastavit úroveň logování.", "loglevel <0-50|{0}>".format("|".join(sorted(self.loglevels, key=self.loglevels.get))))

    def rehash(self, command, args, msg):
        self.bot.rehash()
        return "Rehashnuto, šéfiku."

    def restart(self, command, args, msg):
        self.bot.restart()
        return "Restartováno, šéfiku."

    def die(self, command, args, msg):
        self.bot.die()
        return "Umírám..."

    def loglevel(self, command, args, msg):
        if not args.isdigit():
            args = args.upper()
            if args in self.loglevels:
                args = self.loglevels[args]
            else:
                return "Musíš zadat číslo v rozmezí 0-50, nebo jednu z hodnot {0}.".format(", ".join(sorted(self.loglevels, key=self.loglevels.get)))
        else:
            args = int(args)

        if args < 0 or args > 50:
            return "Musíš zadat číslo v rozmezí 0-50, nebo jednu z hodnot {0}.".format(", ".join(sorted(self.loglevels, key=self.loglevels.get)))

        logging.getLogger("").setLevel(args)
        return "Nastaveno."
