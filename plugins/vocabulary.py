# -*- coding: utf-8 -*-
"""
    plugins/vocabulary.py - A plugin for testing knowledge of defined
    vocabulary.
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

import logging
import re


class vocabulary(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.log = logging.getLogger("keelsbot.vocabulary")
        self.store = vocabularyStore(self.bot.store)
        self.defPCRE = re.compile(" *([^ ]+) +([^ ]+) +(.+?) *\((.*?)\) +(.+?)( *\((.*?)\))? *$")
        self.testing = {}
        self.about = "'Vocabulary' slouží pro ukládání slovíček do slovníku a testování jejich znalostí.\nAutor: Petr Morávek"
        bot.addCommand("createdict", self.createDict, "Vytvořit slovník", "Vytvoří slovník pro ukládání překladů slovíček mezi jazyk1 a jazyk2.", "createdict jazyk1 jazyk2")
        bot.addCommand("listdict", self.listDict, "Seznam slovníků", "Vypíše seznam vytvořených slovníků.", "listdict")
        bot.addCommand("add", self.add, "Přidat slovíčko", "Uloží do databáze překlad slovíčka.", "add jazyk1 jazyk2 slovíčko1 ([poznámka1]) slovíčko2 ([poznámka2])")
        bot.addCommand("del", self.delete, "Smaže slovíčko", "Smaže z databáze překlad slovíčka.", "del jazyk1 jazyk2 slovíčko1 () slovíčko2")
        bot.addCommand("list", self.listVocabulary, "Seznam slovíček", "Vypíše seznam všech slovíček v zadaném slovníku.", "list jazyk1 jazyk2")
        bot.addCommand("start", self.start, "Začít test", "Začne test ze znalosti slovíček jazyk1 > jazyk2.", "start jazyk1 jazyk2")
        bot.addCommand("stop", self.stop, "Ukončit test", "Ukončí probíhající test.", "stop")


    def createDict(self, command, args, msg):
        left = ""
        right = ""
        if args.count(" ") > 0:
            [left, right] = args.split(" ", 1)
            left = left
            right = right
        if len(left) == 0 or len(right) == 0:
            return "Musíš zadat názvy dvou jazyků oddělené mezerou."

        if self.store.findDict(left, right) is not None:
            return "Tento slovník již existuje."

        self.store.createDict(left, right)
        return "OK, vytvořen slovník {0} - {1}.".format(left, right)


    def listDict(self, command, args, msg):
        dicts = []
        for dict in self.store.listDict():
            dicts.append(" - ".join(dict))
        if len(dicts) == 0:
            return "Nemám žádné slovníky."
        return "Seznam slovníků:\n" + "\n".join(dicts)


    def parseArgs(self, args):
        match = self.defPCRE.match(args)
        if match is None:
            return "Neplatný formát."

        dict = self.store.findDict(match.group(1), match.group(2))
        if dict is None:
            return "Tento slovník neexistuje."

        if dict[1]:
            leftPhrase = match.group(5)
            leftNote = match.group(7)
            rightPhrase = match.group(3)
            rightNote = match.group(4)
        else:
            leftPhrase = match.group(3)
            leftNote = match.group(4)
            rightPhrase = match.group(5)
            rightNote = match.group(7)

        return dict[0], leftPhrase, rightPhrase, leftNote, rightNote


    def add(self, command, args, msg):
        parsed = self.parseArgs(args)
        if isinstance(parsed, str):
            return parsed
        else:
            dict, leftPhrase, rightPhrase, leftNote, rightNote = parsed

        self.store.updateVoc(dict, leftPhrase, rightPhrase, leftNote, rightNote)
        return "Uloženo."



    def delete(self, command, args, msg):
        parsed = self.parseArgs(args)
        if isinstance(parsed, str):
            return parsed
        else:
            dict, leftPhrase, rightPhrase, leftNote, rightNote = parsed

        self.store.deleteVoc(dict, leftPhrase, rightPhrase)
        return "Smazáno."


    def listVocabulary(self, command, args, msg):
        left = ""
        right = ""
        if args.count(" ") > 0:
            [left, right] = args.split(" ", 1)
            left = left
            right = right
        if len(left) == 0 or len(right) == 0:
            return "Musíš zadat názvy dvou jazyků oddělené mezerou."

        dict = self.store.findDict(left, right)
        if dict is None:
            return "Tento slovník neexistuje."

        vocabulary = []
        for row in self.store.listVoc(dict):
            if row[2] is not None:
                leftVoc = "{0} ({1})".format(row[0], row[2])
            else:
                leftVoc = row[0]
            if row[3] is not None:
                rightVoc = "{0} ({1})".format(row[1], row[3])
            else:
                rightVoc = row[1]
            vocabulary.append("{0} = {1}".format(leftVoc, rightVoc))

        if len(vocabulary) == 0:
            return "Nemám žádná slovíčka ve slovníku {0} - {1}.".format(left, right)

        return "Slovíčka ve slovníku {0} - {1}:\n".format(left, right) + "\n".join(vocabulary)


    def start(self, command, args, msg):
        pass

    def stop(self, command, args, msg):
        pass

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



class vocabularyStore(object):
    def __init__(self, store):
        self.log = logging.getLogger("keelsbot.vocabulary.store")
        self.store = store
        self.createTables()


    def createTables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS dictionaries (
                        left VARCHAR(15) NOT NULL,
                        right VARCHAR(15) NOT NULL,
                        PRIMARY KEY (left, right))""")

        self.store.query("""CREATE TABLE IF NOT EXISTS vocabulary (
                        dictionary_id INTEGER NOT NULL,
                        left_phrase VARCHAR(100) NOT NULL,
                        left_note VARCHAR(255),
                        right_phrase VARCHAR(100) NOT NULL,
                        right_note VARCHAR(255),
                        PRIMARY KEY (dictionary_id, left_phrase, right_phrase))""")

        self.store.query("""CREATE TABLE IF NOT EXISTS vocabulary_weights (
                        jid VARCHAR(100) NOT NULL,
                        vocabulary_id INTEGER NOT NULL,
                        left INT(2) NOT NULL DEFAULT 5,
                        right INT(2) NOT NULL DEFAULT 5,
                        PRIMARY KEY (jid, vocabulary_id))""")


    def findDict(self, left, right):
        left = left.strip().lower()
        right = right.strip().lower()
        result = self.store.query("SELECT [rowid], [left]=? AS [reverse] FROM [dictionaries] WHERE ([left]=? AND [right]=?) OR ([right]=? AND [left]=?)", (right, left, right, left, right))
        if (len(result) == 0):
            return None
        else:
            return (int(result[0]["rowid"]), result[0]["reverse"] == 1)


    def createDict(self, left, right):
        left = left.strip().lower()
        right = right.strip().lower()
        self.store.query("INSERT INTO dictionaries ([left], [right]) VALUES(?,?)", (left, right))


    def listDict(self):
        dicts = []
        for row in self.store.query("SELECT [left], [right] FROM [dictionaries]"):
            dicts.append((row["left"], row["right"]))
        return dicts


    def updateVoc(self, dict, leftPhrase, rightPhrase, leftNote, rightNote):
        if leftNote is not None and len(leftNote) == 0:
            leftNote = None
        if rightNote is not None and len(rightNote) == 0:
            rightNote = None
        self.store.query("INSERT OR REPLACE INTO [vocabulary] ([dictionary_id], [left_phrase], [right_phrase], [left_note], [right_note]) VALUES(?,?,?,?,?)", (dict, leftPhrase, rightPhrase, leftNote, rightNote))


    def deleteVoc(self, dict, leftPhrase, rightPhrase):
        self.store.query("DELETE FROM [vocabulary] WHERE [dictionary_id]=? AND [left_phrase]=? AND [right_phrase]=?", (dict, leftPhrase, rightPhrase))


    def listVoc(self, dict):
        vocabulary = []
        for row in self.store.query("SELECT [left_phrase], [right_phrase], [left_note], [right_note] FROM [vocabulary] WHERE [dictionary_id]=?", (dict[0],)):
            if dict[1]:
                vocabulary.append((row["right_phrase"], row["left_phrase"], row["right_note"], row["left_note"]))
            else:
                vocabulary.append((row["left_phrase"], row["right_phrase"], row["left_note"], row["right_note"]))
        return vocabulary
