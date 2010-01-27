# -*- coding: utf-8 -*-
"""
    plugins/definitions.py - A plugin for remembering definitions.
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


class definitions(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.log = logging.getLogger("keelsbot.definitions")
        self.store = definitionsStore(self.bot.store)
        self.about = "'Definitions' slouží pro pamatování si definicí a jejich vypisování.\nAutor: Petr Morávek"
        bot.addCommand("!", self.define, "Definice", "Uloží (příp. smaže) definici do databáze.", "! víceslovný název = [definice]")
        bot.addCommand("!!", self.define, "Definice se zámkem", "Uloží (příp. smaže) definici do databáze a uzamkne ji proti editaci uživateli s nižšími právy než autor.", "!! víceslovný název = [definice]")
        bot.addCommand("?", self.query, "Zobrazí definici", "Vrátí požadovanou definici z databáze.", "? víceslovný název")


    def define(self, command, args, msg):
        level = 0
        if command == "!!":
            level = self.bot.getAccessLevel(msg)

        name = None
        description = None
        if args.count("=") > 0:
            [name, description] = args.split("=", 1)
        else:
            return "Něco ti tam chybí, šéfiku!"

        name = name.strip()
        description = description.strip()
        if name is None or name == "":
            return "Musíš zadat, co chceš definovat!"

        storedLevel = self.store.get(name)[1]
        self.log.debug("DEFINITION: stored {0}, user {1}".format(storedLevel, level))
        if storedLevel > level:
            return "Sorry, ale na tuhle editaci nemáš právo."

        if description is None or description == "":
            self.store.delete(name)
            return "Smazáno (pokud to tam teda bylo ;-))"
        else:
            self.store.update(name, description, level)
            return "{0} == {1}".format(name, description)


    def query(self, command, args, msg):
        return self.store.get(args.strip())[0]



class definitionsStore(object):
    def __init__(self, store):
        self.log = logging.getLogger("keelsbot.definitions.store")
        self.store = store
        self.createTables()


    def createTables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS definitions (
                        name VARCHAR(256) PRIMARY KEY,
                        description VARCHAR(256),
                        level INT(4) NOT NULL)""")


    def update(self, name, description, level=0):
        self.log.debug("Updating definiton of '{0}' with level {1}.".format(name, level))
        self.store.query("INSERT OR REPLACE INTO definitions (name, description, level) VALUES(?,?,?)", (name.lower(), description, level))


    def get(self, name):
        result = self.store.query("SELECT description, level FROM definitions WHERE name=?", (name.lower(),))
        if len(result) == 0:
            return ("Vůbec netuším, kdo nebo co je {0}.".format(name), 0)
        return ("{0} == {1}".format(name, result[0]["description"]), result[0]["level"])


    def delete(self, name):
        self.log.debug("Deleting definition of '{0}'.".format(name))
        self.store.query("DELETE FROM definitions WHERE name=?", (name.lower(),))