#!/usr/bin/python2.5
"""
    This file is part of SleekXMPP.

    SleekXMPP is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    SleekXMPP is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with SleekXMPP; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import logging
import sleekxmpp
from optparse import OptionParser
from xml.etree import ElementTree as ET
import os
import time


class example_xmpp_client(sleekxmpp.xmppclient):
	def __init__(self, jid, password, ssl=False, plugin_config = {}, plugin_whitelist=[]):
		sleekxmpp.xmppclient.__init__(self, jid, password, ssl, plugin_config, plugin_whitelist)
		self.add_handler("<message xmlns='jabber:client'><body xmlns='jabber:client'>quit</body></message>", self.custom_quit)
		self.add_event_handler("message", self.print_message)
		self.add_event_handler("got_online", self.now_online)
		self.add_event_handler("got_offline", self.now_offline)
		self.add_event_handler("changed_status", self.changed_status)
		self.add_event_handler("session_start", self.start, threaded=True)
		self.add_event_handler("roster_update", self.show_roster)
		self.replyto = None
	
	def start(self, event):
		#TODO: make this configurable
		self.requestRoster()
		self.sendPresence(ppriority=10)
		self.prompt()
	
	def show_roster(self, event):
		for jid in event:
			print "%s(%s)" % (event[jid]['name'], jid)

	def print_message(self, event):
		print "IM from %s(%s/%s): %s" % (event['name'], event['jid'], event['resource'], event['message'])

	def now_online(self, event):
		print "* %s(%s/%s) got online as %s: %s" % (event['name'], event['jid'], event['resource'], event['type'], event['message'])

	def now_offline(self, event):
		print "* %s(%s/%s) went offline: %s" % (event['name'], event['jid'], event['resource'], event['message'])
	
	def changed_status(self, event):
		print "* %s(%s/%s) %s: %s" % (event['name'], event['jid'], event['resource'], event['type'], event['message'])

	def custom_quit(self, xml):
		print "custom quit was called!"
		self.disconnect()
	
	def prompt(self):
		lastto = None
		while True:
			print ">"
			command_input = raw_input()
			if ' ' in command_input and '/' in command_input:
				command, args = command_input.split(' ', 1)
				if command == '/tell':
					to, message = args.split(' ', 1)
					print "To %s: %s" % (to, message)
					self.sendMessage(to, message)
					lastto = to
				elif command == '/t':
					if lastto:
						print "To %s: %s" % (lastto, args)
						self.sendMessage(lastto, args)
					else:
						print "Need to /tell a specific JID first."
				elif command == '/r':
					if self.replyto:
						print "To %s: %s" % (self.replyto, args)
						self.sendMessage(self.replyto, args)
					else:
						print "Need to /tell a specific JID first."
				elif command == '/quit':
					self.disconnect()
				elif command == '/join':
					room, nick = args.split(' ', 1)
					self.plugin['xep_0045'].joinMUC(room, nick)
				elif command == '/leave':
					room, nick = args.split(' ', 1)
					self.plugin['xep_0045'].leaveMUC(room, nick)
				elif command == '/testform':
					form = self.plugin['xep_0004'].makeForm('form', 'Test Form', 'Please fill me out!')
					form.addField('crap', label='Fill in some crap')
					form.field['crap'].require()
					self.send(form.getXMLMessage(args))
			if not con.connected:
				break

if __name__ == '__main__':
	#parse command line arguements
	optp = OptionParser()
	optp.add_option('-q','--quiet', help='set logging to ERROR', action='store_const', dest='loglevel', const=logging.ERROR, default=logging.INFO)
	optp.add_option('-d','--debug', help='set logging to DEBUG', action='store_const', dest='loglevel', const=logging.DEBUG, default=logging.INFO)
	optp.add_option('-v','--verbose', help='set logging to COMM', action='store_const', dest='loglevel', const=5, default=logging.INFO)
	optp.add_option("-c","--config", dest="configfile", default="config.xml", help="set config file to use")
	opts,args = optp.parse_args()
	
	logging.basicConfig(level=opts.loglevel, format='%(levelname)-8s %(message)s')

	#load xml config
	logging.info("Loading config file: %s" % opts.configfile)
	config = ET.parse(os.path.expanduser(opts.configfile)).find('auth')
	
	#init
	logging.info("Logging in as %s" % config.attrib['jid'])
	
	
	plugin_config = {}
	plugin_config['xep_0092'] = {'name': 'SleekXMPP Example', 'version': '0.1-dev'}
	plugin_config['xep_0199'] = {'keepalive': True, 'timeout': 30, 'frequency': 300}
	
	con = example_xmpp_client(config.attrib['jid'], config.attrib['pass'], plugin_config=plugin_config, plugin_whitelist=[])
	if not config.get('server', None):
		# we don't know the server, but the lib can probably figure it out
		con.connect() 
	else:
		con.connect((config.attrib['server'], 5222))
	con.process()
	while con.connected:
		time.sleep(1)
