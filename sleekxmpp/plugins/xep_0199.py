"""
	SleekXMPP: The Sleek XMPP Library
	XEP-0199 (Ping) support
	Copyright (C) 2007  Kevin Smith
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
from xml.etree import cElementTree as ET
import base
import time
import logging

class xep_0199(base.base_plugin):
	"""XEP-0199 XMPP Ping"""

	def plugin_init(self):
		self.description = "XMPP Ping"
		self.xep = "0199"
		self.xmpp.add_handler("<iq type='get' xmlns='jabber:client'><ping xmlns='urn:xmpp:ping'/></iq>", self.handler_ping)
		if self.config.get('keepalive', True):
			self.xmpp.add_event_handler('session_start', self.handler_pingserver, threaded=True)
	
	def post_init(self):
		self.xmpp['xep_0030'].add_feature('urn:xmpp:ping')
	
	def handler_pingserver(self, xml):
		error = None
		while error is None:
			time.sleep(self.config.get('frequency', 300))
			error = self.sendPing(self.xmpp.server, self.config.get('timeout', 30))[1]
		logging.debug("Did not recieve ping back in time.  Requesting Reconnect.")
		self.xmpp.requestReconnect()
	
	def handler_ping(self, xml):
		iq = self.xmpp.makeIqResult(xml.get('id', 'unknown'))
		iq.attrib['to'] = xml.get('from', self.xmpp.server)
		self.xmpp.send(iq)

	def sendPing(self, jid, timeout = 30):
		""" sendPing(jid, timeout)
		Sends a ping to the specified jid, returning the time (in seconds)
		to receive a reply, and error or None.
		"""
		id = self.xmpp.getNewId()
		iq = self.xmpp.makeIq(id)
		iq.attrib['type'] = 'get'
		iq.attrib['to'] = jid
		ping = ET.Element('{urn:xmpp:ping}ping')
		iq.append(ping)
		startTime = time.time()
		pingresult = self.xmpp.send(iq, self.xmpp.makeIq(id), timeout)
		endTime = time.time()
		if pingresult == False:
			error = "timed out"
		else:
			error = pingresult.find('{jabber:client}error')
			if error is not None:
				error = "%s: %s" % (error.get('code'), error.getchildren()[0].tag.split('}',1)[1])
		return [endTime - startTime, error]
