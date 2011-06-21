# -*- coding: utf-8 -*-
"""
definitions plugin: remember definitions.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class definitions:
    def __init__(self, bot, config):
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext
        self.store = Storage(bot.store)

        bot.add_command("!", self.define, __("Definition"), __("Stores (or deletes) the definition in database."), __("multiword expression = [definition]"))
        bot.add_command("!!", self.define, __("Definition with lock"), __("Stores (or deletes) the definition in database and locks the definition against change by users with lower privileges than the author."), __("multiword expression = [definition]"))
        bot.add_command("?", self.query, __("Display definition"), __("Display the definition stored in database"), __("multiword expression"))

    def define(self, command, args, msg, uc):
        if args.count("=") > 0:
            name, description = args.split("=", 1)
        else:
            return self.gettext("Didn't you forget something?", uc.lang)

        name = name.strip()
        description = description.strip()
        if name == "":
            return self.gettext("You must specify what term you want to define!", uc.lang)

        stored_level = self.store.get(name)[1]
        if stored_level > uc.level:
            return self.gettext("Sorry, you don't have permission to edit this definition.", uc.lang)

        if description == "":
            self.store.delete(name)
            return self.gettext("Deleted (if there even was something ;-))", uc.lang)
        else:
            if command == "!!":
                level = uc.level
            else:
                level = 0
            self.store.update(name, description, level)
            return name + " == " + description

    def query(self, command, args, msg, uc):
        name = args.strip()
        description = self.store.get(name)[0]
        if description is None:
            return self.gettext("I have no idea, who or what is {}.", uc.lang).format(name)
        else:
            return name + " == " + description


class Storage:
    def __init__(self, store):
        self.store = store
        self.create_tables()

    def create_tables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS definitions (
                            name VARCHAR(256) NOT NULL PRIMARY KEY,
                            description VARCHAR(256) NOT NULL,
                            level INT(4) NOT NULL)""")

    def get(self, name):
        result = self.store.query("SELECT description, level FROM definitions WHERE name=?", (name.lower(),))
        if len(result) == 0:
            return None, 0
        return result[0]["description"], result[0]["level"]

    def update(self, name, description, level=0):
        log.debug(_("Updating definiton of {!r} with level {}.").format(name, level))
        self.store.query("INSERT OR REPLACE INTO definitions (name, description, level) VALUES(?,?,?)", (name.lower(), description, level))

    def delete(self, name):
        log.debug(_("Deleting definition of {!r}.").format(name))
        self.store.query("DELETE FROM definitions WHERE name=?", (name.lower(),))
