# This Python file uses the following encoding: utf-8
"""
    pingbot.py - A plugin for pinging Jids.
    Copyright (C) 2007 Kevin Smith
    Translation by Petr Morávek

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

class pingbot(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = u"'Pingbot' umožňuje uživatelům pingnout jiné JIDy.\nAutor: Kevin Smith"
        self.bot.addCommand('ping', self.handle_ping, 'Ping', u"Zobrazuje odezvu k zadanému JIDu, případně v MUCu podle přezdívky.", 'ping [jid|nick]')

    def handle_ping(self, command, args, msg):
	args = args.split(' ',1)[0]
	if msg['type'] == 'groupchat' and args in self.bot.plugin['xep_0045'].getRoster(msg['room']):
	    jid = "%s/%s" % (msg['room'], args)
	elif msg.get('jid') in self.bot.rooms and args in self.bot.plugin['xep_0045'].getRoster(msg['jid']):
	    jid = "%s/%s" % (msg['jid'], args)
	else:
	    jid = args

	[latency,error] = self.bot['xep_0199'].sendPing(jid, 5)
        response = u"Odezva od %s: %dms." % (args, latency*1000)
	if error is not None:
	    response = response + " (%s)" % error
        return response
