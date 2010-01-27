# -*- coding: utf-8 -*-
"""
    plugins/muc_stability.py - A plugin for keeping a bot in MUC channels
    it joins.
    Copyright (C) 2008 Kevin Smith
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
import threading
import time


class muc_stability(object):
    def __init__(self, bot, config):
        self.log = logging.getLogger("keelsbot.muc_stability")
        self.bot = bot
        self.about = "'MUC_stability' se snaží udržet KeelsBota v kanále.\nAutoři: Kevin Smith, Petr Morávek"
        self.shuttingDown = False
        threading.Thread(target=self.loop).start()
        self.bot.add_handler("<message xmlns='jabber:client' type='error'><error type='modify' code='406' ><not-acceptable xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/></error></message>", self.messageError)


    def loop(self):
        """ Perform the MUC checking.
        """
        while not self.shuttingDown:
            time.sleep(600)
            if self.bot.plugin["xep_0045"]:
                for muc in self.bot.plugin["xep_0045"].getJoinedRooms():
                    jid = self.bot.plugin["xep_0045"].getOurJidInRoom(muc)
                    self.bot.sendMessage(jid, None, mtype="chat")


    def messageError(self, xml):
        """ On error messages, see if it's from a muc, and rejoin the muc if so.
            (Subtle as a flying mallet)
        """
        source = xml.attrib["from"]
        room = self.bot.getjidbare(source)
        if room not in self.bot.plugin["xep_0045"].getJoinedRooms():
            return
        nick = self.bot.getjidresource(self.bot.plugin["xep_0045"].getOurJidInRoom(room))
        self.log.debug("Error from {0}, rejoining as {1}.".format(room, nick))
        self.bot.plugin["xep_0045"].joinMUC(room, nick)


    def shutDown(self):
        self.shuttingDown = True
        #self.bot.del_handler("<message xmlns='jabber:client' type='error'><error type='modify' code='406' ><not-acceptable xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/></error></message>", self.handle_message_error)

