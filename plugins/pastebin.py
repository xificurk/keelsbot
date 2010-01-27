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
        default = config.findall("default")[0]
        self.lang = default.get("lang", "text")
        self.expiration = default.get("expiration", "d")
        self.about = "'Pastebin' umožňuje odeslání kódu na pastebin.cz.\nAutor: Petr Morávek"
        self.bot.addCommand("paste", self.paste, "Pastebin", "Odešle kód na pastebin.cz.\nNa prvním řádku bere v libovolném pořadí oddělené mezerou platnost (d - den, w - týden, m - měsíc, y - rok; výchozí hodnota je {0}), název jazyku (podle http://www.pastebin.cz/info/api, výchozí hodnota je {1}), a zda odeslat vygenerovaný odkaz přímo do MUCu (1, výchozí hodnota je 0, tzn. poslat odkaz zpátky odkud přišel požadavek).\nNa druhém řádku je titulek (může být prázdný).\nNa všech dalších řádcích je samotný kód.".format(self.expiration, self.lang), "paste [d|w|m|y] [lang] [0|1]\nTitulek\nKód")


    def paste(self, command, args, msg):
        paste = args.split("\n", 2)
        self.log.debug(paste)
        if len(paste) < 3:
            return "Neplatné zadání, mrkni na help."

        sendToMUC = 0
        lang = self.lang
        expiration = self.expiration

        title = paste[1]
        code = paste[2]

        arguments = paste[0].split(" ")
        for param in arguments:
            if param in ["d", "w", "m", "y"]:
                expiration = param
            elif param == "0" or param == "1":
                sendToMUC = int(param)
            elif param != "":
                lang = param

        if expiration == "d":
            expiration = 1
        elif expiration == "w":
            expiration = 2
        elif expiration == "m":
            expiration = 3
        else:
            expiration = 4

        if msg["type"] == "groupchat":
            author = msg["mucnick"]
        elif msg["from"].bare in self.bot.rooms:
            author = msg["from"].resource
        else:
            author = msg["from"].user

        data = {"service_id":2, "service_adapter":"remote_adapter", "user_api_key":"d1e70fb6f3010769b8ea3252965aef41", "text":code, "author":author, "expiration":expiration, "language":lang}
        if title != "":
            data["title"] = title

        response = urllib.request.urlopen("http://www.pastebin.cz/remote", urllib.parse.urlencode(data), 10)
        if response.getcode() != 201:
            return "ERROR"
        url = response.readline().decode("utf-8")

        if sendToMUC == 1 and msg["type"] != "groupchat" and msg["from"].bare in self.bot.rooms:
            self.bot.sendMessage(msg["from"].bare, "{0} vložil {1}".format(author, url), mtype="groupchat")
        else:
            return str(url)
