#!/usr/bin/python2.5

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
#from __future__ import absolute_import
from basexmpp import basexmpp
from xml.etree import cElementTree as ET
from xmlstream import xmlstream
from xmlstream import RestartStream
from xmlstream import filesocket
from xmlstream import hassub
from xmlstream import isET
import plugins
import time
import logging
import base64
import md5
import sys
import random
import copy
srvsupport = True
try:
	import dns.resolver
except ImportError:
	srvsupport = False

class xmppclient(basexmpp):
	"""SleekXMPP's client class.  Use only for good, not evil."""

	def __init__(self, jid, password, ssl=False, plugin_config = {}, plugin_whitelist=[]):
		global srvsupport
		basexmpp.__init__(self)
		self.plugin_config = plugin_config
		self.set_jid(jid)
		self.plugin_whitelist = plugin_whitelist
		self.auto_reconnect = True
		self.auto_authorize = True
		self.auto_subscribe = True
		self.srvsupport = srvsupport
		self.password = password
		self.registered_features = []
		self.default_ns = 'jabber:client'
		self.streamheader = """<stream:stream to='%s' xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client' version='1.0'>""" % (self.server,)
		self.streamfooter = "</stream:stream>"
		self.map_namespace('http://etherx.jabber.org/streams', 'stream')
		self.map_namespace('jabber:client', '')
		self.plugin = {}
		self.features = []
		self.authenticated = False
		self.sessionstarted = False
		self.roster = {}
		self.event_handlers = {}
		self.add_handler("<message xmlns='jabber:client' type='chat'><body /></message>", self.handler_message)
		self.add_handler("<message xmlns='jabber:client' type='normal'><body /></message>", self.handler_message)
		self.add_handler("<message xmlns='jabber:client' type='__None__'><body /></message>", self.handler_message)
		self.add_handler("<features xmlns='http://etherx.jabber.org/streams'/>", self.handler_stream_features, False, True)
		self.add_handler("<presence xmlns='jabber:client' type='available'/>", self.handler_presence)
		self.add_handler("<presence xmlns='jabber:client' type='__None__'/>", self.handler_presence)
		self.add_handler("<presence xmlns='jabber:client' type='unavailable'/>", self.handler_presence)
		self.add_handler("<iq xmlns='jabber:client' type='set'><query xmlns='jabber:iq:roster' /></iq>", self.handler_roster_set, threaded=True)
		self.add_handler("<presence xmlns='jabber:client' type='subscribe' />", self.handler_presence_subscribe, threaded=True)
		self.registerFeature("<starttls xmlns='urn:ietf:params:xml:ns:xmpp-tls' />", self.handler_starttls, True)
		self.registerFeature("<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl' />", self.handler_sasl_auth, True)
		self.registerFeature("<bind xmlns='urn:ietf:params:xml:ns:xmpp-bind' />", self.handler_bind_resource)
		self.registerFeature("<session xmlns='urn:ietf:params:xml:ns:xmpp-session' />", self.handler_start_session)
		self.register_plugins()
	
	def __getitem__(self, key):
		if self.plugin.has_key(key):
			return self.plugin[key]
		else:
			logging.warning("""Plugin "%s" is not loaded.""" % key)
			return False
	
	def get(self, key, default):
		return self.plugin.get(key, default)

	def connect(self, address=tuple()):
		"""Connect to the Jabber Server.  Attempts SRV lookup, and if it fails, uses
		the JID server."""
		if not address or len(address) < 2:
			if not self.srvsupport:
				logging.debug("Did not supply (address, port) to connect to and no SRV support is installed (http://www.dnspython.org).  Continuing to attempt connection, using server hostname from JID.")
			else:
				logging.debug("Since no address is supplied, attempting SRV lookup.")
				try:
					answers = dns.resolver.query("_xmpp-client._tcp.%s" % self.server, "SRV")
				except dns.resolver.NXDOMAIN:
					logging.debug("No appropriate SRV record found.  Using JID server name.")
				else:
					# pick a random answer, weighted by priority
					# there are less verbose ways of doing this (random.choice() with answer * priority), but I chose this way anyway 
					# suggestions are welcome
					addresses = {}
					intmax = 0
					priorities = []
					for answer in answers:
						intmax += answer.priority
						addresses[intmax] = (answer.target.to_text()[:-1], answer.port)
						priorities.append(intmax) # sure, I could just do priorities = addresses.keys()\n priorities.sort()
					picked = random.randint(0, intmax)
					for priority in priorities:
						if picked <= priority:
							address = addresses[priority]
							break
		if not address:
			# if all else fails take server from JID.
			address = (self.server, 5222)
		result = xmlstream.connect(self, address)
		if result:
			self.event("connected")
		else:
			self.event("disconnected")
		return result
	
	# overriding reconnect and disconnect so that we can get some events
	# should events be part of or required by xmlstream?  Maybe that would be cleaner
	def reconnect(self):
		self.event("disconnected")
		xmlstream.reconnect(self)
	
	def disconnect(self, init=True, close=False):
		self.event("disconnected")
		xmlstream.disconnect(self, init, close)
	
	def registerFeature(self, mask, pointer, breaker = False):
		"""Register a stream feature."""
		with self.lock:
			self.registered_features.append((mask, pointer, breaker))

	def registerPlugin(self, plugin, pconfig = {}):
		"""Register a plugin not in plugins.__init__.__all__ but in the plugins
		directory."""
		# discover relative "path" to the plugins module from the main app, and import it.
		__import__("%s.%s" % (globals()['plugins'].__name__, plugin))
		# init the plugin class
		self.plugin[plugin] = getattr(getattr(plugins, plugin), plugin)(self, pconfig) # eek
		# all of this for a nice debug? sure.
		xep = ''
		if hasattr(self.plugin[plugin], 'xep'):
			xep = "(XEP-%s) " % self.plugin[plugin].xep
		logging.debug("Loaded Plugin %s%s" % (xep, self.plugin[plugin].description))

	def updateRoster(self, jid, name=None, subscription=None, groups=[]):
		"""Add or change a roster item."""
		iq = self.makeIqSet()
		iq.attrib['from'] = self.fulljid
		query = self.makeQueryRoster(iq)
		item = ET.Element('item')
		item.attrib['jid'] = jid
		if name:
			item.attrib['name'] = name
		if subscription in ['to', 'from', 'both']:
			item.attrib['subscription'] = subscription
		else:
			item.attrib['subscription'] = 'none'
		for group in groups:
			groupxml = ET.Element('group')
			groupxml.text = group
			item.append.groupxml
		return self.send(iq, self.makeIq(self.getId()))
	
	def requestRoster(self):
		"""Request the roster be sent."""
		roster = self.send(self.makeIqGet('jabber:iq:roster'), self.makeIqResult(self.getId()))
		if roster is not False:
			self.handler_roster_set(roster)
		else:
			logging.warning("Did not retrieve roster.")
	
	def register_plugins(self):
		"""Initiates all plugins in the plugins/__init__.__all__"""
		if self.plugin_whitelist:
			plugin_list = self.plugin_whitelist
		else:
			plugin_list = plugins.__all__
		for plugin in plugin_list:
			if plugin in plugins.__all__:
				self.registerPlugin(plugin, self.plugin_config.get(plugin, {}))
			else:
				raise NameError, "No plugin by the name of %s listed in plugins.__all__." % plugin
		# run post_init() for cross-plugin interaction
		for plugin in self.plugin:
			self.plugin[plugin].post_init()
	
	def set_jid(self, jid):
		"""Rip a JID apart and claim it as our own."""
		with self.lock:
			self.fulljid = jid
			self.resource = self.getjidresource(jid)
			self.jid = self.getjidbare(jid)
			self.username = jid.split('@', 1)[0]
			self.server = jid.split('@',1)[-1].split('/', 1)[0]
		
	def handler_stream_features(self, xml):
		for subelement in xml:
			for feature in self.registered_features:
				if self.maskcmp(subelement, feature[0], True):
					if apply(feature[1], (subelement,)) and feature[2]: #if breaker, don't continue
						return True
	
	def handler_starttls(self, xml):
		if self.tls_support:
			self.add_handler("<proceed xmlns='urn:ietf:params:xml:ns:xmpp-tls' />", self.handler_tls_start)
			self.send(xml)
			return True
		else:
			logging.warning("The module tlslite is required in to some servers, and has not been found.")
			return False

	def handler_tls_start(self, xml):
		logging.debug("Starting TLS")
		if self.enable_tls():
			raise RestartStream
	
	def handler_sasl_auth(self, xml):
		logging.debug("Starting SASL Auth")
		self.add_handler("<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl' />", self.handler_auth_success)
		self.add_handler("<failure xmlns='urn:ietf:params:xml:ns:xmpp-sasl' />", self.handler_auth_fail)
		sasl_mechs = xml.findall('{urn:ietf:params:xml:ns:xmpp-sasl}mechanism')
		if len(sasl_mechs):
			for sasl_mech in sasl_mechs:
				with self.lock:
					self.features.append("sasl:%s" % sasl_mech.text)
			if 'sasl:PLAIN' in self.features:
				self.send("""<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='PLAIN'>%s</auth>""" % (base64.b64encode('\x00%s\x00%s' % (self.username, self.password))))
			else:
				logging.error("No appropriate login method.")
				self.disconnect()
				#if 'sasl:DIGEST-MD5' in self.features:
				#	self._auth_digestmd5()
		return True
	
	def handler_auth_success(self, xml):
		with self.lock:
			self.authenticated = True
			self.features = []
		raise RestartStream

	def handler_auth_fail(self, xml):
		logging.info("Authentication failed.")
		self.disconnect()
		self.event("failed_auth")
	
	def handler_bind_resource(self, xml):
		logging.debug("Requesting resource: %s" % self.resource)
		out = self.makeIqSet()
		res = ET.Element('resource')
		res.text = self.resource
		xml.append(res)
		out.append(xml)
		response = self.send(out, self.makeIqResult(self.getId()))
		self.set_jid(response.find('{urn:ietf:params:xml:ns:xmpp-bind}bind/{urn:ietf:params:xml:ns:xmpp-bind}jid').text)
		logging.info("Node set to: %s" % self.fulljid)
	
	def handler_start_session(self, xml):
		if self.authenticated:
			response = self.send(self.makeIqSet(xml), self.makeIq(self.getId()))
			logging.debug("Established Session")
			with self.lock:
				self.sessionstarted = True
			self.event("session_start")
	
	def handler_roster_set(self, xml):
		roster_update = {}
		with self.lock:
			for item in xml.findall('{jabber:iq:roster}query/{jabber:iq:roster}item'):
				if not self.roster.has_key(item.attrib['jid']):
					self.roster[item.attrib['jid']] = {'groups': [], 'name': '', 'subscription': 'none', 'presence': {}, 'in_roster': False}
				self.roster[item.attrib['jid']]['name'] = item.get('name', '')
				self.roster[item.attrib['jid']]['subscription'] = item.get('subscription', 'none')
				self.roster[item.attrib['jid']]['in_roster'] = 'True'
				for group in item.findall('{jabber:iq:roster}group'):
					self.roster[item.attrib['jid']]['groups'].append(group.text)
				if self.roster[item.attrib['jid']]['groups'] == []:
					self.roster[item.attrib['jid']]['groups'].append('Default')
				roster_update[item.attrib['jid']] = self.roster[item.attrib['jid']]
		if xml.get('type', 'result') == 'set':
			self.send(self.makeIqResult(xml.get('id', '0')))
		self.event("roster_update", roster_update)
	
	def handler_message(self, xml):
		mfrom = xml.attrib['from']
		message = xml.find('{jabber:client}body').text
		subject = xml.find('{jabber:client}subject')
		if subject is not None:
			subject = subject.text
		else:
			subject = ''
		resource = self.getjidresource(mfrom)
		mfrom = self.getjidbare(mfrom)
		mtype = xml.attrib.get('type', 'normal')
		name = self.roster.get('name', '')
		self.event("message", {'jid': mfrom, 'resource': resource, 'name': name, 'type': mtype, 'subject': subject, 'message': message})
	
	def handler_presence(self, xml):
		"""Update roster items based on presence"""
		show = xml.find('{jabber:client}show')
		status = xml.find('{jabber:client}status')
		priority = xml.find('{jabber:client}priority')
		fulljid = xml.attrib['from']
		resource = self.getjidresource(fulljid)
		if not resource:
			resouce = None
		jid = self.getjidbare(fulljid)
		if type(status) == type(None) or status.text is None:
			status = ''
		else:
			status = status.text
		if type(show) == type(None): 
			show = 'available'
		else:
			show = show.text
		if xml.get('type', None) == 'unavailable':
			show = 'unavailable'
		if type(priority) == type(None):
			priority = 0
		else:
			priority = int(priority.text)
		wasoffline = False
		with self.lock:
			oldroster = self.roster.get(jid, {}).get(resource, {})
			if not self.roster.has_key(jid):
					self.roster[jid] = {'groups': [], 'name': '', 'subscription': 'none', 'presence': {}, 'in_roster': False}
			if not self.roster[jid]['presence'].has_key(resource):
				wasoffline = True
				self.roster[jid]['presence'][resource] = {'show': show, 'status': status, 'priority': priority}
			else:
				if self.roster[jid]['presence'][resource].get('show', None) == 'unavailable':
					wasoffline = True
				self.roster[jid]['presence'][resource] = {'show': show, 'status': status}
				if priority:
					self.roster[jid]['presence'][resource]['priority'] = priority
		name = self.roster[jid].get('name', '')
		eventdata = {'jid': jid, 'resource': resource, 'name': name, 'type': show, 'priority': priority, 'message': status}
		if wasoffline and show in ('available', 'away', 'xa', 'na'):
			self.event("got_online", eventdata)
		elif not wasoffline and show == 'unavailable':
			self.event("got_offline", eventdata)
		elif oldroster != self.roster.get(jid, {'presence': {}})['presence'].get(resource, {}) and show != 'unavailable':
			self.event("changed_status", eventdata)
		name = ''
		if name:
			name = "(%s) " % name
		logging.debug("STATUS: %s%s/%s[%s]: %s" % (name, jid, resource, show,status))
	
	def handler_presence_subscribe(self, xml):
		"""Handling subscriptions automatically."""
		if self.auto_authorize == True:
			self.updateRoster(self.getjidbare(xml.attrib['from']))
			self.send(self.makePresence(ptype='subscribed', pto=self.getjidbare(xml.attrib['from'])))
			if self.auto_subscribe:
				self.send(self.makePresence(ptype='subscribe', pto=self.getjidbare(xml.attrib['from'])))
		elif self.auto_authorize == False:
			self.send(self.makePresence(ptype='unsubscribed', pto=self.getjidbare(xml.attrib['from'])))
		elif self.auto_authorize == None:
			pass
