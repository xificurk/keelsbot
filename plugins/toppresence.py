# This Python file uses the following encoding: utf-8
"""
    plugins/toppresence.py - A plugin for tracking current and maximum number
    of users in MUC.
    Copyright (C) 2009 Petr Morávek

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

import datetime
import time
import logging

class toppresencestore(object):
    def __init__(self, store):
        self.store = store
        self.createTable()

    def createTable(self):
        db = self.store.getDb()
        if not len(db.execute("pragma table_info('toppresence')").fetchall()) > 0:
            db.execute("""CREATE TABLE toppresence (
                       muc VARCHAR(256) PRIMARY KEY, users INTEGER)""")
        db.close()

    def update(self, muc, number):
        db = self.store.getDb()
        cur = db.cursor()
        logging.debug("Updating toppresence")
        cur.execute('SELECT * FROM toppresence WHERE muc=?', (muc,))
        if (len(cur.fetchall()) > 0):
            cur.execute('UPDATE toppresence SET muc=?, users=? WHERE muc=?', (muc, number, muc))
            logging.debug("Updated existing toppresence")
        else:
            cur.execute('INSERT INTO toppresence(muc, users) VALUES(?,?)',(muc, number))
            logging.debug("Added new toppresence")
        db.commit()
        db.close()

    def get(self, muc):
        db = self.store.getDb()
        cur = db.cursor()
        cur.execute('SELECT users FROM toppresence WHERE muc=? LIMIT 1', (muc,))
        results = cur.fetchall()
        if len(results) == 0:
            return 0
        return results[0][0]
        db.close()

class toppresence(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.store = toppresencestore(self.bot.store)
        self.about = u"'TopPresence' sleduje počet uživatelů v MUCu a hlásí, když je dosažen rekord.\nAutor: Petr Morávek"
        self.bot.add_event_handler("groupchat_presence", self.handle_groupchat_presence, threaded=True)
        self.bot.addCommand('cu', self.handle_cu, u'Počet uživatelů v MUCu', u"Vypíše aktuální počet uživatelů v MUCu.", u'cu')
        self.bot.addCommand('mu', self.handle_mu, u'Maximální počet uživatelů v MUCu', u"Vypíše historicky nejvyšší počet uživatelů v MUCu.", u'mu')

    def handle_groupchat_presence(self, presence):
        """ Keep track of the presences in mucs.
        """
        muc = presence.get('room', None)
        if muc == None or muc not in self.bot.rooms:
            return
        actual = len(self.bot.plugin['xep_0045'].getRoster(muc))
        time.sleep(3)
        actual = max(len(self.bot.plugin['xep_0045'].getRoster(muc)), actual)
        stored = self.store.get(muc)

        if actual > stored:
            self.store.update(muc, actual)
            self.bot.sendMessage("%s" % muc, u"V místnosti je historicky nejvyšší počet uživatelů (%d)." % actual, mtype='groupchat')

    def handle_cu(self, command, args, msg):
        if msg['type'] == 'groupchat':
            muc = msg.get('room', None)
        else:
            muc = msg.get('jid', None)
        if muc == None or muc not in self.bot.rooms:
            return

        actual = len(self.bot.plugin['xep_0045'].getRoster(muc))
        return u'Momentálně tu vidím %d uživatelů.' % actual

    def handle_mu(self, command, args, msg):
        if msg['type'] == 'groupchat':
            muc = msg.get('room', None)
        else:
            muc = msg.get('jid', None)
        if muc == None or muc not in self.bot.rooms:
            return

        stored = self.store.get(muc)
        return u'Viděl jsem tu nanejvýše %d uživatelů najednou.' % stored

    def shutDown(self):
        self.bot.del_event_handler("groupchat_presence", self.handle_groupchat_presence, threaded=True)
