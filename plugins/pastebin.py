# -*- coding: utf-8 -*-
"""
    plugins/pastebin.py - A plugin for sending code snippets to pastebin.cz.
    Copyright (C) 2009-2010 Petr Morávek

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
import urllib


class pastebin(object):
    def __init__(self, bot, config):
        self.log = logging.getLogger("keelsbot.pastebin")
        self.bot = bot
        self.lang = config.get("lang", "text")
        self.expiration = config.get("expiration", "1D")
        self.about = "'Pastebin' umožňuje odeslání kódu na pastebin.com.\nAutor: Petr Morávek"
        self.bot.addCommand("paste", self.paste, "Pastebin", "Odešle kód na pastebin.com.\nNa prvním řádku bere v libovolném pořadí oddělené mezerou platnost (10M = 10 minut, 1H = 1 hodina, 1D = 1 den, 1M = 1 měsíc, N = navždy; výchozí hodnota je {0}), název jazyku (podle http://pastebin.com/api.php, výchozí hodnota je {1}), a zda odeslat vygenerovaný odkaz přímo do MUCu (1, výchozí hodnota je 0, tzn. poslat odkaz zpátky odkud přišel požadavek).\nNa všech dalších řádcích je samotný kód.".format(self.expiration, self.lang), "paste [10M|1H|1D|1M|N] [lang] [0|1]\nKód")


    def paste(self, command, args, msg):
        paste = args.split("\n", 1)
        self.log.debug(paste)
        if len(paste) < 2:
            return "Neplatné zadání, mrkni na help."

        sendToMUC = 0
        lang = self.lang
        expiration = self.expiration

        code = paste[1]

        arguments = paste[0].split(" ")
        for param in arguments:
            if param.upper() in ["10M", "1H", "1D", "1M", "N"]:
                expiration = param.upper()
            elif param == "0" or param == "1":
                sendToMUC = int(param)
            elif param != "":
                lang = param

        if msg["type"] == "groupchat":
            author = msg["mucnick"]
        elif msg["from"].bare in self.bot.rooms:
            author = msg["from"].resource
        else:
            author = msg["from"].user

        data = {"paste_code":code, "paste_name":author, "paste_expire_date":expiration, "paste_format":lang}
        self.log.debug(data)

        try:
            response = urllib.request.urlopen("http://pastebin.com/api_public.php", urllib.parse.urlencode(data), 10)
        except IOError:
            self.log.error("Could not fetch pastebin.")
            return "ERROR"
        if response.getcode() != 200:
            self.log.error("Got error code {0} from pastebin.".format(response.getcode()))
            return "ERROR {0}".format(response.getcode())

        url = response.readline().decode("utf-8")

        if sendToMUC == 1 and msg["type"] != "groupchat" and msg["from"].bare in self.bot.rooms:
            self.bot.sendMessage(msg["from"].bare, "{0} vložil {1}".format(author, url), mtype="groupchat")
        else:
            return str(url)
