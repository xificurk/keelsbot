# This Python file uses the following encoding: utf-8
"""
    pastebin.py - A plugin for returning links to comics from MaFian liFe.
    Copyright (C) 2009 Petr Morávek

    KeelsBot is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    KeelsBot is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this software; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import logging
import urllib

class pastebin(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        default = self.config.findall('default')[0]
        self.lang = default.get('lang', 'text')
        self.expiration = default.get('expiration', 'd')
        self.about = u"'Pastebin' umožňuje odeslání kódu na pastebin.cz.\nAutor: Petr Morávek"
        self.bot.addCommand('paste', self.handle_paste, 'Pastebin', u"Odešle kód na pastebin.cz.\nNa prvním řádku bere v libovolném pořadí oddělené mezerou platnost (d - den, w - týden, m - měsíc, y - rok; výchozí hodnota je %s), název jazyku (podle http://www.pastebin.cz/info/api, výchozí hodnota je %s), a zda odeslat vygenerovaný odkaz přímo do MUCu (1, výchozí hodnota je 0, tzn. poslat odkaz zpátky odkud přišel požadavek).\nNa druhém řádku je titulek (může být prázdný).\nNa všech dalších řádcích je samotný kód." % (self.expiration, self.lang), u"paste [d|w|m|y] [lang] [0|1]\nTitulek\nKód")

    def handle_paste(self, command, args, msg):
        paste = args.split("\n", 2)
        logging.debug(paste)
        if len(paste) < 3:
            return u"Neplatné zadání, mrkni na !help paste."

        sendToMUC = 0
        lang = self.lang
        expiration = self.expiration

        title = paste[1]
        code = paste[2]

        arguments = paste[0].split(" ")
        for param in arguments:
            if param in ['d', 'w', 'm', 'y']:
                expiration = param
            elif param == "0" or param == "1":
                sendToMUC = int(param)
            elif param != '':
                lang = param

        if expiration == 'd':
            expiration = 1
        elif expiration == 'w':
            expiration = 2
        elif expiration == 'm':
            expiration = 3
        else:
            expiration = 4

        if msg['type'] == 'groupchat':
            author = msg['name']
        elif msg.get('jid', '') in self.bot.rooms:
            author = msg['resource']
        else:
            author = msg['jid'].split('@',1)[0]

        data = {"service_id":2,"service_adapter":"remote_adapter","user_api_key":"d1e70fb6f3010769b8ea3252965aef41","text":code,"author":author,"expiration":expiration,"language":lang}
        if title != '':
            data['title'] = title

        #response = urllib.urlopen("http://www.pastebin.cz/remote",urllib.urlencode(data))
        #if response.getcode() != 201:
            #return "ERROR"
        #url = response.readline()
        url = "TESTING"

        if sendToMUC == 1 and msg['type'] != 'groupchat' and msg['jid'] in self.bot.rooms:
            self.bot.sendMessage("%s" % msg['jid'], "%s vložil %s" % (author, url), mtype='groupchat')
        else:
            return "%s" % url