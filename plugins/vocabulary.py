# -*- coding: utf-8 -*-
"""
vocabulary plugin: Tests knowledge of defined vocabulary.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging
import random
import re

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class vocabulary:
    _re_definition = re.compile(" *([^ ]+) +([^ ]+) +(.+?) *\((.*?)\) +(.+?)( *\((.*?)\))? *$")
    testing = {}

    def __init__(self, bot, config):
        self.cmd_prefix = bot.cmd_prefix
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext
        self.store = Storage(bot.store)

        bot.add_command("createdict", self.create_dictionary, __("Create dictionary"), __("Creates dictionary for storing phrase translations between lang1 and lang2"), __("lang1 lang2"))
        bot.add_command("listdict", self.list_dictionary, __("List of dictionaries"), __("Display the list of dictionaries."))
        bot.add_command("add", self.add_vocabulary, __("Add phrase"), __("Stores the translation of the phrase."), __("lang1 lang2 phrase1 ([note1]) phrase2 ([note2])"))
        bot.add_command("del", self.delete_vocabulary, __("Delete phrase"), __("Deletes the translation of the phrase."), __("lang1 lang2 phrase1 () phrase2"))
        bot.add_command("list", self.list_vocabulary, __("List vocabulary"), __("Display the list of stored translations in the dictionary."), __("lang1 lang2"))
        bot.add_command("start", self.start, __("Start test"), __("Starts the test of phrase translations lang1 > lang2."), __("lang1 lang2"))
        bot.add_command("stop", self.stop, __("Stop test"), __("Stops the current test."))
        bot.add_event_handler("message", self.handle_message, threaded=True)

    def shutdown(self, bot):
        bot.del_event_handler("message", self.handle_message)

    def handle_message(self, msg):
        jid = msg["from"].bare
        if jid not in self.testing:
            return

        answer = msg.get("body", "").strip()
        if answer.startswith(self.cmd_prefix):
            return

        reply = msg.reply()
        data = self.testing[jid]
        if answer == data["current"]["answer"]:
            data["current"]["weight"] = max(min(data["current"]["weight"]-1, 9), 0)
        else:
            data["current"]["weight"] = max(min(data["current"]["weight"]+1, 9), 0)
            reply["body"] = self.gettext("WRONG! Correct answer: {}", data["lang"]).format(data["current"]["answer"])
            reply.send()
        self.store.set_weight(data["dictionary"][1], jid, data["current"])
        data["current"] = self._get_random(data["choices"], exclude=data["current"]["id"])
        reply["body"] = data["current"]["query"]
        reply.send()

    def create_dictionary(self, command, args, msg, uc):
        parsed = self._parse_dictionary(args, uc.lang)
        if isinstance(parsed, str):
            return parsed
        else:
            left, right = parsed

        if self.store.find_dictionary(left, right) is not None:
            return self.gettext("This dictionary already exists.", uc.lang)

        self.store.create_dictionary(left, right)
        return self.gettext("Dictionary {} - {} created.", uc.lang).format(left, right)

    def list_dictionary(self, command, args, msg, uc):
        dictionaries = []
        for dictionary in self.store.list_dictionary():
            dictionaries.append(" - ".join(dictionary))
        if len(dictionaries) == 0:
            return self.gettext("No dictionaries found.", uc.lang)
        return self.gettext("Dictionaries", uc.lang) + ":\n" + "\n".join(dictionaries)

    def add_vocabulary(self, command, args, msg, uc):
        parsed = self._parse_translation(args, uc.lang)
        if isinstance(parsed, str):
            return parsed

        self.store.update_vocabulary(*parsed)
        return self.gettext("Saved.", uc.lang)

    def delete_vocabulary(self, command, args, msg, uc):
        parsed = self._parse_translation(args, uc.lang)
        if isinstance(parsed, str):
            return parsed
        else:
            dictionary, left_phrase, right_phrase, left_note, right_note = parsed

        self.store.delete_vocabulary(dictionary, left_phrase, right_phrase)
        return self.gettext("Deleted.", uc.lang)

    def list_vocabulary(self, command, args, msg, uc):
        parsed = self._parse_dictionary(args)
        if isinstance(parsed, str):
            return parsed
        else:
            left, right = parsed

        dictionary = self.store.find_dictionary(left, right)
        if dictionary is None:
            return self.gettext("This dictionary does not exist.", uc.lang)

        vocabulary = []
        for row in self.store.list_vocabulary(*dictionary):
            if row[2] is not None:
                left_voc = "{} ({})".format(row[0], row[2])
            else:
                left_voc = row[0]
            if row[3] is not None:
                right_voc = "{} ({})".format(row[1], row[3])
            else:
                right_voc = row[1]
            vocabulary.append("{} = {}".format(left_voc, right_voc))

        if len(vocabulary) == 0:
            return self.gettext("No phrases in dictionary {} - {}.", uc.lang).format(left, right)

        return self.gettext("Vocabulary from dictionary {} - {}", uc.lang).format(left, right) + ":\n" + "\n".join(vocabulary)

    def start(self, command, args, msg, uc):
        parsed = self._parse_dictionary(args, uc.lang)
        if isinstance(parsed, str):
            return parsed
        else:
            left, right = parsed

        dictionary = self.store.find_dictionary(left, right)
        if dictionary is None:
            return self.gettext("This dictionary does not exist.", uc.lang)

        jid = msg["from"].bare
        choices = self.store.get_vocabulary(dictionary[0], dictionary[1], jid)
        if len(choices) == 0:
            return self.gettext("The dictionary is empty!", uc.lang)

        current = self._get_random(choices)
        self.testing[jid] = {"dictionary":dictionary, "choices":choices, "current":current, "lang":uc.lang}
        return current["query"]

    def stop(self, command, args, msg, uc):
        jid = msg["from"].bare
        if jid in self.testing:
            del self.testing[jid]
        return self.gettext("OK", uc.lang)

    def _parse_dictionary(self, args, lang):
        left = ""
        right = ""
        if args.count(" ") > 0:
            left, right = args.split(" ", 1)
        if len(left) == 0 or len(right) == 0:
            return self.gettext("You must supply names of two languages separated by space.", lang)
        return left, right

    def _parse_translation(self, args, lang):
        match = self._re_definition.match(args)
        if match is None:
            self.gettext("Invalid format.", lang)

        dictionary = self.store.find_dictionary(match.group(1), match.group(2))
        if dictionary is None:
            return self.gettext("This dictionary does not exist.", lang)

        if dictionary[1]:
            left_phrase = match.group(5)
            left_note = match.group(7)
            right_phrase = match.group(3)
            right_note = match.group(4)
        else:
            left_phrase = match.group(3)
            left_note = match.group(4)
            right_phrase = match.group(5)
            right_note = match.group(7)

        return dictionary[0], left_phrase, right_phrase, left_note, right_note

    def _get_random(self, choices, exclude=None):
        if len(choices) == 1:
            return choices[0]

        sum_ = 0
        for item in choices:
            if exclude == item["id"]:
                continue
            sum_ += 2**item["weight"]

        length = len(choices)
        if exclude is not None:
            length -= 1
        log.debug(_("Randomly choosing from {} choices (weight sum {}).").format(length, sum_))

        select = random.randint(1, sum_)
        sum_ = 0
        for item in choices:
            if exclude == item["id"]:
                continue
            sum_ += 2**item["weight"]
            if select <= sum_:
                return item


class Storage:
    def __init__(self, store):
        self.store = store
        self.create_tables()

    def create_tables(self):
        with self.store.lock:
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
                            left INT(1) NOT NULL DEFAULT 5,
                            right INT(1) NOT NULL DEFAULT 5,
                            PRIMARY KEY (jid, vocabulary_id))""")

    def find_dictionary(self, left, right):
        left = left.strip().lower()
        right = right.strip().lower()
        with self.store.lock:
            result = self.store.query("SELECT [rowid], [left]=? AS [reverse] FROM [dictionaries] WHERE ([left]=? AND [right]=?) OR ([right]=? AND [left]=?)", (right, left, right, left, right))
        if (len(result) == 0):
            return None
        else:
            return (int(result[0]["rowid"]), result[0]["reverse"] == 1)

    def create_dictionary(self, left, right):
        left = left.strip().lower()
        right = right.strip().lower()
        with self.store.lock:
            self.store.query("INSERT INTO dictionaries ([left], [right]) VALUES(?,?)", (left, right))

    def list_dictionary(self):
        dictionaries = []
        with self.store.lock:
            for row in self.store.query("SELECT [left], [right] FROM [dictionaries]"):
                dictionaries.append((row["left"], row["right"]))
        return dictionaries

    def update_vocabulary(self, dictionary, left_phrase, right_phrase, left_note, right_note):
        if left_note is not None and len(left_note) == 0:
            left_note = None
        if right_note is not None and len(right_note) == 0:
            right_note = None
        with self.store.lock:
            self.store.query("INSERT OR REPLACE INTO [vocabulary] ([dictionary_id], [left_phrase], [right_phrase], [left_note], [right_note]) VALUES(?,?,?,?,?)", (dictionary, left_phrase, right_phrase, left_note, right_note))

    def delete_vocabulary(self, dictionary, left_phrase, right_phrase):
        with self.store.lock:
            self.store.query("DELETE FROM [vocabulary] WHERE [dictionary_id]=? AND [left_phrase]=? AND [right_phrase]=?", (dictionary, left_phrase, right_phrase))

    def list_vocabulary(self, dictionary, reverse):
        vocabulary = []
        with self.store.lock:
            for row in self.store.query("SELECT [left_phrase], [right_phrase], [left_note], [right_note] FROM [vocabulary] WHERE [dictionary_id]=?", (dictionary,)):
                if reverse:
                    vocabulary.append((row["right_phrase"], row["left_phrase"], row["right_note"], row["left_note"]))
                else:
                    vocabulary.append((row["left_phrase"], row["right_phrase"], row["left_note"], row["right_note"]))
        return vocabulary

    def get_vocabulary(self, dictionary, reverse, jid):
        if reverse:
            side_query = "right"
            side_answer = "left"
        else:
            side_query = "left"
            side_answer = "right"
        vocabulary = []
        with self.store.lock:
            db = self.store.get_db()
            for row in db.cursor().execute("SELECT [rowid], [left_phrase], [right_phrase], [left_note], [right_note] FROM [vocabulary] WHERE [dictionary_id]=?", (dictionary,)).fetchall():
                phrase = {"id":row["rowid"]}
                weight = db.cursor().execute("SELECT [{}] FROM [vocabulary_weights] WHERE jid=? AND vocabulary_id=?".format(side_query), (jid, row["rowid"])).fetchone()
                if weight is not None:
                    phrase["weight"] = int(weight[side])
                else:
                    phrase["weight"] = 5
                if row[side_query+"_note"] is not None:
                    phrase["query"] = "{} ({})".format(row[side_query+"_phrase"], row[side_query+"_note"])
                else:
                    phrase["query"] = row[side_query+"_phrase"]
                phrase["answer"] = row[side_answer+"_phrase"]
                vocabulary.append(phrase)
            db.close()
        return vocabulary

    def set_weight(self, reverse, jid, phrase):
        with self.store.lock:
            if reverse:
                self.store.query("INSERT OR REPLACE INTO [vocabulary_weights] (jid, vocabulary_id, right) VALUES(?,?,?)", (jid, phrase["id"], phrase["weight"]))
            else:
                self.store.query("INSERT OR REPLACE INTO [vocabulary_weights] (jid, vocabulary_id, left) VALUES(?,?,?)", (jid, phrase["id"], phrase["weight"]))
