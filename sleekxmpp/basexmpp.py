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
from xml.etree import cElementTree as ET
from xmlstream import xmlstream
#from xmlstream import RestartStream
from xmlstream import hassub
from xmlstream import isET
import logging
import thread

class basexmpp(xmlstream):
	def __init__(self):
		xmlstream.__init__(self)
		self.id = 0
		self.id_lock = thread.allocate_lock()
		self.stanza_errors = {
			'bad-request':False,
			'conflict':False,
			'feature-not-implemented':False,
			'forbidden':False,
			'gone':True,
			'internal-server-error':False,
			'item-not-found':False,
			'jid-malformed':False,
			'not-acceptable':False,
			'not-allowed':False,
			'payment-required':False,
			'recipient-unavailable':False,
			'redirect':True,
			'registration-required':False,
			'remote-server-not-found':False,
			'remote-server-timeout':False,
			'resource-constraint':False,
			'service-unavailable':False,
			'subscription-required':False,
			'undefined-condition':False,
			'unexpected-request':False}
		self.stream_errors = {
			'bad-format':False,
			'bad-namespace-prefix':False,
			'conflict':False,
			'connection-timeout':False,
			'host-gone':False,
			'host-unknown':False,
			'improper-addressing':False,
			'internal-server-error':False,
			'invalid-from':False,
			'invalid-id':False,
			'invalid-namespace':False,
			'invalid-xml':False,
			'not-authorized':False,
			'policy-violation':False,
			'remote-connection-failed':False,
			'resource-constraint':False,
			'restricted-xml':False,
			'see-other-host':True,
			'system-shutdown':False,
			'undefined-condition':False,
			'unsupported-encoding':False,
			'unsupported-stanza-type':False,
			'unsupported-version':False,
			'xml-not-well-formed':False}
		self.sentpresence = False
	
	def getNewId(self):
		with self.id_lock:
			self.id += 1
			return self.getId()
	
	def getId(self):
		return "%x".upper() % self.id
	
	def makeIq(self, id=0):
		iq = ET.Element('{jabber:client}iq')
		if id == 0:
			id = self.getNewId()
		iq.set('id', str(id))
		return iq
	
	def makeIqGet(self, queryxmlns = None):
		iq = self.makeIq()
		iq.set('type', 'get')
		if queryxmlns:
			query = ET.Element("{%s}query" % queryxmlns)
			iq.append(query)
		return iq
	
	def makeIqResult(self, id):
		iq = self.makeIq(id)
		iq.set('type', 'result')
		return iq
	
	def makeIqSet(self, sub=None):
		iq = self.makeIq()
		iq.set('type', 'set')
		if sub != None:
			iq.append(sub)
		return iq

	def makeIqError(self, id):
		iq = self.makeIq(id)
		iq.set('type', 'error')
		return iq

	def makeStanzaErrorCondition(self, condition, cdata=None):
		if condition not in self.stanza_errors:
			raise ValueError()
		stanzaError = ET.Element('{urn:ietf:params:xml:ns:xmpp-stanzas}'+condition)
		if cdata is not None:
			if not self.stanza_errors[condition]:
				raise ValueError()
			stanzaError.text = cdata
		return stanzaError


	def makeStanzaError(self, condition, errorType, code=None, text=None, customElem=None):
		if errorType not in ['auth', 'cancel', 'continue', 'modify', 'wait']:
			raise ValueError()
		error = ET.Element('error')
		error.append(condition)
		error.set('type',errorType)
		if code is not None:
			error.set('code', code)
		if text is not None:
			textElem = ET.Element('text')
			textElem.text = text
			error.append(textElem)
		if customElem is not None:
			error.append(customElem)
		return error

	def makeStreamErrorCondition(condition, cdata=None):
		if condition not in self.stream_errors:
			raise ValueError()
		streamError = ET.Element('{urn:ietf:params:xml:ns:xmpp-streams}'+condition)
		if cdata is not None:
			if not self.stream_errors[condition]:
				raise ValueError()
			textElem = ET.Element('text')
			textElem.text = text
			streamError.append(textElem)

	def makeStreamError(errorElem, text=None):
		error = ET.Element('error')
		error.append(errorElem)
		if text is not None:
			textElem = ET.Element('text')
			textElem.text = text
			error.append(text)
		return error

	def makeIqQuery(self, iq, xmlns):
		query = ET.Element("{%s}query" % xmlns)
		iq.append(query)
		return iq
	
	def makeQueryRoster(self, iq=None):
		query = ET.Element("{jabber:iq:roster}query")
		if iq:
			iq.append(query)
		return query
	
	def add_event_handler(self, name, pointer, threaded=False, disposable=False):
		if not self.event_handlers.has_key(name):
			with self.lock:
				self.event_handlers[name] = []
		with self.lock:
			self.event_handlers[name].append((pointer, threaded, disposable))

	def event(self, name, eventdata = {}): # called on an event
		for handler in self.event_handlers.get(name, []):
			if handler[1]: #if threaded
				thread.start_new(handler[0], (eventdata,))
			else:
				apply(handler[0], (eventdata,))
			if handler[2]: #disposable
				with self.lock:
					self.event_handlers[name].pop(self.event_handlers[name].index(handler))
	
	def makeMessage(self, mto, mbody='', msubject=None, mtype=None):
		message = ET.Element('{jabber:client}message')
		message.attrib['from'] = self.fulljid
		message.attrib['to'] = mto
		if not mtype:
			mtype='chat'
		message.attrib['type'] = mtype
		if mbody:
			body = ET.Element('body')
			body.text = mbody
			message.append(body)
		if msubject:
			subject = ET.Element('subject')
			subject.text = msubject
			message.append(subject)
		return message
	
	def makePresence(self, pshow=None, pstatus=None, ppriority=None, pto=None, ptype=None):
		presence = ET.Element('{jabber:client}presence')
		if ptype:
			presence.attrib['type'] = ptype
		if pshow:
			show = ET.Element('show')
			show.text = pshow
			presence.append(show)
		if pstatus:
			status = ET.Element('status')
			status.text = pstatus
			presence.append(status)
		if ppriority:
			priority = ET.Element('priority')
			priority.text = str(ppriority)
			presence.append(priority)
		if pto:
			presence.attrib['to'] = pto
		return presence
	
	def sendMessage(self, mto, mbody, msubject=None, mtype=None):
		self.send(self.makeMessage(mto,mbody,msubject,mtype))
	
	def sendPresence(self, pshow=None, pstatus=None, ppriority=None, pto=None):
		self.send(self.makePresence(pshow,pstatus,ppriority,pto))
		if not self.sentpresence:
			self.event('sent_presence')
			self.sentpresence = True
	
	def getjidresource(self, fulljid):
		if '/' in fulljid:
			return fulljid.split('/', 1)[-1]
		else:
			return ''
	
	def getjidbare(self, fulljid):
		return fulljid.split('/', 1)[0]
