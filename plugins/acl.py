# -*- coding: utf-8 -*-
"""
    plugins/acl.py - A plugin for managing ACLs.
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

class acl(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.about = "'Acl' umožňuje zjistit přístupová práva uživatelů podle JID.\nAutor: Petr Morávek"
        bot.addCommand("level", self.level, "Level", "Vypíše úroveň přístupu odesilatele.", "level")

    def level(self, command, args, msg):
        level = self.bot.getAccessLevel(msg)
        return "Jsi na levelu {0}.".format(level)
