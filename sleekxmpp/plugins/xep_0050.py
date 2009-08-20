"""
	SleekXMPP: The Sleek XMPP Library
	Copyright (C) 2007  Nathanael C. Fritz
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
from __future__ import with_statement
import base
import logging
from xml.etree import cElementTree as ET
import traceback
import time
import thread

class xep_0050(base.base_plugin):
	"""
	XEP-0050 Ad-Hoc Commands
	"""
	
	def plugin_init(self):
		self.xep = '0050'
		self.description = 'Ad-Hoc Commands'
		self.xmpp.add_handler("<iq type='set' xmlns='jabber:client'><command xmlns='http://jabber.org/protocol/commands' action='__None__'/></iq>", self.handler_command)
		self.xmpp.add_handler("<iq type='set' xmlns='jabber:client'><command xmlns='http://jabber.org/protocol/commands' action='execute'/></iq>", self.handler_command)
		self.xmpp.add_handler("<iq type='set' xmlns='jabber:client'><command xmlns='http://jabber.org/protocol/commands' action='next'/></iq>", self.handler_command_next, threaded=True)
		self.xmpp.add_handler("<iq type='set' xmlns='jabber:client'><command xmlns='http://jabber.org/protocol/commands' action='cancel'/></iq>", self.handler_command_cancel)
		self.commands = {}
		self.sessions = {}
	
	def post_init(self):
		self.xmpp['xep_0030'].add_feature('http://jabber.org/protocol/commands')

	def addCommand(self, node, name, form, pointer=None, multi=False):
		self.xmpp['xep_0030'].add_item(self.xmpp.fulljid, name, 'http://jabber.org/protocol/commands', node)
		self.xmpp['xep_0030'].add_identity('automation', 'command-node', name, node)
		self.xmpp['xep_0030'].add_feature('http://jabber.org/protocol/commands', node)
		self.xmpp['xep_0030'].add_feature('jabber:x:data', node)
		self.commands[node] = (name, form, pointer, multi)
	
	def getNewSession(self):
		return str(time.time()) + '-' + self.xmpp.getNewId()
	
	def handler_command(self, xml):
		in_command = xml.find('{http://jabber.org/protocol/commands}command')
		sessionid = in_command.get('sessionid', None)
		node = in_command.get('node')
		sessionid = self.getNewSession()
		name, form, pointer, multi = self.commands[node]
		self.sessions[sessionid] = {}
		self.sessions[sessionid]['past'] = [(form, None)]
		self.sessions[sessionid]['next'] = pointer
		npointer = pointer
		if multi:
			actions = ['next']
			status = 'executing'
		else:
			status = 'completed'
			actions = []
		self.xmpp.send(self.makeCommand(xml.attrib['from'], in_command.attrib['node'], form=form, id=xml.attrib['id'], sessionid=sessionid, status=status, actions=actions))
	
	def handler_command_next(self, xml):
		in_command = xml.find('{http://jabber.org/protocol/commands}command')
		sessionid = in_command.get('sessionid', None)
		pointer = self.sessions[sessionid]['next']
		results = self.xmpp['xep_0004'].makeForm('result')
		results.fromXML(in_command.find('{jabber:x:data}x'))
		form, npointer, next = apply(pointer, (results,sessionid))
		self.sessions[sessionid]['next'] = npointer
		self.sessions[sessionid]['past'].append((form, pointer))
		actions = []
		actions.append('prev')
		if npointer is None:
			status = 'completed'
		else:
			status = 'executing'
			if next:
				actions.append('next')
			else:
				actions.append('finish')
		self.xmpp.send(self.makeCommand(xml.attrib['from'], in_command.attrib['node'], form=form, id=xml.attrib['id'], sessionid=sessionid, status=status, actions=actions))
		
	def handler_command_cancel(self, xml):
		command = xml.find('{http://jabber.org/protocol/commands}command')
		try:
			del self.sessions[command.get('sessionid')]
		except:
			pass
		self.xmpp.send(self.makeCommand(xml.attrib['from'], command.attrib['node'], id=xml.attrib['id'], sessionid=command.attrib['sessionid'], status='canceled'))

	def makeCommand(self, to, node, id=None, form=None, sessionid=None, status='executing', actions=[]):
		if not id:
			id = self.xmpp.getNewId()
		iq = self.xmpp.makeIqResult(id)
		iq.attrib['from'] = self.xmpp.fulljid
		iq.attrib['to'] = to
		command = ET.Element('{http://jabber.org/protocol/commands}command')
		command.attrib['node'] = node
		command.attrib['status'] = status
		xmlactions = ET.Element('actions')
		for action in actions:
			xmlactions.append(ET.Element(action))
		if xmlactions:
			command.append(xmlactions)
		if not sessionid:
			sessionid = self.getNewSession()
		command.attrib['sessionid'] = sessionid
		if form:
			if hasattr(form,'getXML'):
				form = form.getXML()
			command.append(form)
		iq.append(command)
		return iq
