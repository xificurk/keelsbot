# -*- coding: utf-8 -*-
"""
    plugins/texy.py - A plugin for parsing Texy! syntax.
    Copyright (C) 2010 Petr Morávek

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

import os.path
from subprocess import getoutput


class texy(object):
    def __init__(self, bot, config):
        self.texy = "php {0}".format(os.path.join(os.path.dirname(__file__), "..", "misc", "texy.process.php"))
        self.about = "'Texy' parsuje zprávy pomocí Texy!.\nAutor: Petr Morávek"
        bot.addCommand("texy", self.process, "Texy!", "Zpracuje zprávu pomocí Texy! Pokud není předána žádná zpráva, vypíše verzi Texy!", "texy [zpráva]")

    def process(self, command, args, msg):
        if args == "":
            return "Texy! {0}".format(getoutput(self.texy))
        return getoutput("{0} '{1}'".format(self.texy, args.replace("'", "\\'")))
