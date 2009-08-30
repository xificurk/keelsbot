# This Python file uses the following encoding: utf-8
"""
    plugins/definitionbot.py - A plugin for remembering definitions.
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

class definitionstore(object):
    def __init__(self, store):
        self.store = store
        self.createTable()

    def createTable(self):
        db = self.store.getDb()

        if not len(db.execute("pragma table_info('definitions')").fetchall()) > 0:
            db.execute("""CREATE TABLE definitions (
                       name VARCHAR(256) PRIMARY KEY,
                       description VARCHAR(256))""")
        db.close()
    
    def update(self, name, description):
        db = self.store.getDb()
        cur = db.cursor()
        logging.debug("Updating definitions")
        cur.execute('SELECT * FROM definitions WHERE name=?', (name.lower(),))
        if (len(cur.fetchall()) > 0):
            cur.execute('UPDATE definitions SET name=?, description=? WHERE name=?', (name.lower(), description, name.lower()))
            logging.debug("Updated existing definition")
        else:
            cur.execute('INSERT INTO definitions(name, description) VALUES(?,?)',(name.lower(), description))
            logging.debug("Added new definition")
        db.commit()
        db.close()
    
    def get(self, name):
        db = self.store.getDb()
        cur = db.cursor()
        cur.execute('SELECT description FROM definitions WHERE name=?', (name.lower(),))
        results = cur.fetchall()
        if len(results) == 0:
            return u"Vůbec netuším, kdo nebo co je " + name + "."
        return name + " == " + results[0][0]
        db.close()
    
    def delete(self, name):
        db = self.store.getDb()
        cur = db.cursor()
        cur.execute('DELETE FROM definitions WHERE name=?', (name.lower(),))
        db.commit()
        db.close()


class definitionbot(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.definitionstore = definitionstore(self.bot.store)
        self.about = u"'Definitionbot' slouží pro pamatování si definicí a jejich vypisování.\nAutor: Petr Morávek"
        self.bot.addCommand('!', self.handle_definition, 'Definice', u"Uloží definici do databáze.", u"! víceslovný název = [definice]")
        self.bot.addCommand('?', self.handle_query, 'Dotaz na definici', u"Vrátí požadovanou definici z databáze.", u"? víceslovný název")

    def handle_definition(self, command, args, msg):
        name = None
        description = None
        if args.count("=") > 0:
            [name, description] = args.split("=",1)
        else:
            return u"Něco ti tam chybí, šéfiku!"
        name = name.strip()
        description = description.strip()

        if name != None and name != "":
            if description == None or description == "":
                self.definitionstore.delete(name)
                response = u"Smazáno (pokud to tam teda bylo ;-))"
            else:
                self.definitionstore.update(name, description)
                response = name + " == " + description
        else:
            return u"Musíš zadat, co chceš definovat!"

        logging.debug("handle_definition done: %s" % response)
        return response


    def handle_query(self, command, args, msg):
        response = self.definitionstore.get(args.strip())

        logging.debug("handle_query done: %s" % response)
        return response
