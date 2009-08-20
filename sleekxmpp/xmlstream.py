from __future__ import with_statement
from xml.etree import cElementTree as ET
from xml.parsers.expat import ExpatError
import socket
import logging
import thread
import Queue
import traceback
import time
import types
tls_support = True
try:
	from tlslite.api import *
except ImportError:
	tls_support = False
	class TLSAbruptCloseError(Exception):
		pass
	class TLSAlert(Exception):
		pass
	class TLSAuthenticationError(Exception):
		pass

logging.COMM = 5
logging.addLevelName(5, 'COMM')

class RestartStream(Exception):
	pass

class CleanDisconnect(Exception):
	pass

class ReconnectNow(Exception):
	pass

class filesocket(object):
	"""Special socket override that adds a read() method so that ElementTree.iterparse can use it.
	Also handles logging.COMM logging of what was recieved."""

	def __init__(self, socket):
		self.socket = socket

	def read(self, amount=1024):
		readbuffer = ''
		try:
			readbuffer = self.socket.recv(amount)
		except TLSAlert:
			logging.log(logging.ERROR, "TLS Alert")
			logging.log(logging.DEBUG, traceback.format_exc())
		except socket.error, (errno, strerror):
			if errno == 104:
				logging.log(logging.DEBUG, "Remote end closed prematurely.")
			else:
				raise
		except: #TODO flesh out exceptions
			logging.log(logging.DEBUG, "Exception raised in socket.recv()")
			logging.log(logging.DEBUG, traceback.format_exc())
		if readbuffer.strip():
			logging.log(logging.COMM, "RECV: %s" % readbuffer)
		return readbuffer

def isET(xmlobj):
	return hasattr(xmlobj, 'tag')

def hassub(xmlobj, search, namespace=None):
	if namespace:
		namespace = "{%s}" % namespace
	else:
		namespace = ''
	return isET(xmlobj.find("%s%s" % (namespace, search)))


class xmlstream(object):
	"""Deal with any XML stream, including server listeners. Includes feature
	mapping using masks called "handlers." """
	def __init__(self, xmlns=''):
		self.recv_handler = []
		self.send_handler = []
		self.start_handler = []
		self.end_handler = []
		self.default_ns = ''
		self.namespace_map = {}
		self.streamheader = u"<stream>"
		self.streamfooter = u"</stream>"
		self.waitingxml = {}
		self.connected = False
		self.addr = None
		self.conntype = 'client'
		self.basetag = 'stream'
		self.listener = False
		self.basens = None
		self.auto_reconnect = True
		self.gotstart = False
		self.lock = thread.allocate_lock()
		self.use_ssl = False
		self.tlsconn = None
		self.nanny_queue = None
		self.initing_close = False
		global tls_support
		self.tls_support = tls_support
		self.realsocket = None
	
	def enable_tls(self):
		if self.tls_support:
			with self.lock:
				self.realsocket = self.socket
				self.socket = TLSConnection(self.socket)
				self.socket.handshakeClientCert()
				self.file = filesocket(self.socket)
			return True
		else:
			logging.warning("Tried to enable TLS, but tlslite module not found.")
			return False

	def maskcmp(self, source, maskobj, use_ns=False, default_ns='__no_ns__'):
		"""maskcmp(xmlobj, maskobj):
		Compare etree xml object to etree xml object mask"""
		#TODO require namespaces
		if source == None: #if element not found (happens during recursive check below)
			return False
		if type(maskobj) == type(str()): #if the mask is a string, make it an xml obj
			try:
				maskobj = ET.fromstring(maskobj)
			except ExpatError, (text):
				logging.log(logging.WARNING, "Expat error: %s\nIn parsing: %s" % (text, maskobj))
		if not use_ns and source.tag.split('}', 1)[-1] != maskobj.tag.split('}', 1)[-1]: # strip off ns and compare
			return False
		if use_ns and (source.tag != maskobj.tag and "{%s}%s" % (self.default_ns, maskobj.tag) != source.tag ):
			return False
		if maskobj.text and source.text != maskobj.text:
			return False
		for attr_name in maskobj.attrib: #compare attributes
			if source.attrib.get(attr_name, "__None__") != maskobj.attrib[attr_name]:
				return False
		#for subelement in maskobj.getiterator()[1:]: #recursively compare subelements
		for subelement in maskobj: #recursively compare subelements
			if not self.maskcmp(source.find(subelement.tag), subelement, use_ns):
				return False
		return True

	def xmlesc(self, text):
		text = "%s" % text
		text = text.replace("&", "&amp;")
		text = text.replace("<", "&lt;")
		text = text.replace("\"", "&quot;")
		text = text.replace(">", "&gt;")
		text = text.replace("'", "&apos;")
		return text

	def tounicode(self, val, encoding='utf-8'):
		if type(val) != types.UnicodeType:
			##return val.encode(encoding, 'backslashreplace')
			return unicode(val, encoding, 'ignore')
		else:
			return val
	
	def map_namespace(self, ns, shortcut):
		self.namespace_map[shortcut] = ns

	def tostring(self, xml, xmlns=u'', stringbuffer=u''):
		#TODO respect ET mapped namespaces
		itag = self.tounicode(xml.tag.split('}', 1)[-1])
		if '}' in xml.tag:
			ixmlns = self.tounicode(xml.tag.split('}', 1)[0][1:])
		else:
			ixmlns = u''
		nsbuffer = u''
		if xmlns != ixmlns and ixmlns != u'':
			if self.namespace_map.has_key(ixmlns):
				if self.namespace_map[ixmlns] != '':
					itag = u"%s:%s" % (self.tounicode(self.namespace_map[ixmlns]), itag)
			else:
				nsbuffer = u""" xmlns="%s\"""" % ixmlns
		stringbuffer += u"<%s" % itag
		stringbuffer += nsbuffer
		for attrib in xml.attrib:
			stringbuffer += u""" %s="%s\"""" % (self.tounicode(attrib), self.tounicode(self.xmlesc(xml.attrib[attrib])))
		if len(xml):
			stringbuffer += u">"
			for child in xml.getchildren():
				stringbuffer += self.tostring(child, ixmlns)
			stringbuffer += u"</%s>" % (itag, )
		elif xml.text:
			stringbuffer += u">%s</%s>" % (self.tounicode(self.xmlesc(xml.text)), itag)
		else:
			stringbuffer += u" />"
		return stringbuffer

	def connect(self, addr):
		"""connect(addr):
		addr is a tuple (host, port)"""
		logging.log(logging.DEBUG, "Connecting via client method to %s:%s" % (addr[0], addr[1]))
		self.conntype = 'client'
		try:
			self.addr = addr
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.socket.connect(addr)
			if self.use_ssl:
				self.tlsconn = TLSConnection(self.socket)
				try:
					self.tlsconn.handshakeClientSharedKey("shared", "key")
				except (TLSLocalAlert):
					logging.log(logging.ERROR, "Incoming connection failed TLS handshake")
					return False
		except socket.error, (errno, strerror):
			logging.log(logging.ERROR, "Could not connect. Socket error #%s: %s" % (errno, strerror))
			return False
		with self.lock:
			self.connected = True
		self._send(self.streamheader)
		return True

	def connect_unix(self, addr):
		"""connect_unix(file):
		Connect to a unix socket"""
		logging.log(logging.DEBUG, "Connecting via unix socket to %s" % (addr, ))
		self.conntype = 'unix'
		self.addr = addr
		try:
			self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			self.socket.connect(addr)
		except socket.error, (errno, strerror):
			logging.log(logging.ERROR, "Could not connect. Socket error #%s: %s" % (errno, strerror))
			return False
		with self.lock:
			self.connected = True
		self._send(self.streamheader)
		return True

	def connect_socket(self, socket, listener=True):
		"""connect_socket(socket, listener):
		Connect to a pre-existing socket.
		Listener optional.  Set to True if xmlstream is a daemon connection."""
		self.listener = listener
		self.conntype = 'socket'
		self.socket = socket
		if not listener:
			self._send(self.streamheader)
		self.connected = True
		return True
	
	def _failed_disconnect(self):
		logging.debug("Starting failsafe disconnect.")
		time.sleep(5)
		if self.connected:
			logging.warning("Didn't recieve end of stream in time.  Closing down.")
			self.socket.close()
			self.connected = False

	def disconnect(self, init=True, close=False):
		logging.log(logging.DEBUG, "Disconnecting.")
		try:
			if not self.initing_close:
				self._send(self.streamfooter, None, None, True)
				logging.debug("sending end of stream")
			if init:
				thread.start_new(self._failed_disconnect, tuple())
				if self.nanny_queue:
					self.nanny_queue.put(0)
				if self.realsocket: # TLS doesn't pass through shutdown
					self.realsocket.shutdown(1)
				else:
					self.socket.shutdown(1)
				self.initing_close = True
			if close:
				logging.debug("Closing socket")
				self.socket.close()
				if (self.initing_close or not self.auto_reconnect) and self.listener:
					logging.debug("Setting connected to False")
					self.connected = False
		except socket.error, (errno, strerror):
			logging.warning("Error disconnecting.  Ignoring.")

	def reconnect(self):
		self.disconnect(init=False, close=True)
		if not self.auto_reconnect:
			if self.nanny_queue:
				self.nanny_queue.put(0)
			self.connected = False
			return False
		logging.log(logging.DEBUG, "Attempting reconnect.")
		result = None
		while not result:
			if self.conntype == 'client':
				result = self.connect(self.addr)
			elif self.conntype == 'unix':
				result = self.connect_unix(self.addr)
			if not result:
				time.sleep(5)
		return True

	def post_reconnect(self):
		"""To be overridden.  Called by process nanny after a reconnect and _process"""
		pass

	def add_send_handler(self, xmlobj, pointer, disposable=False, threaded=False, filter=False):
		"""add_send_handler(maskxml, pointer, disposable, threaded, filter)"""
		with self.lock:
			self.send_handler.append((xmlobj, pointer, disposable, threaded, filter))

	#def add_handler(self, xmlobj, pointer, disposable=False, threaded=False, filter = False, sr='recv'):
	def add_handler(self, xmlobj, pointer, disposable=False, threaded=False, filter = False):
		"""add_handler(maskxml, pointer, disposable, threaded, filter)"""
		with self.lock:
			self.recv_handler.append((xmlobj, pointer, disposable, threaded, filter))

	def add_start_handler(self, pointer):
		"""add_start_handler(pointer):
		Adds pointer to call when stream starts"""
		with self.lock:
			self.start_handler.append(pointer)

	def add_end_handler(self, pointer):
		"""add_end_handler(pointer):
		Adds pointer to call when stream ends"""
		with self.lock:
			self.end_handler.append(pointer)

	def _map_namespace(self, key, value):
		"""_map_namespace(key, value):
		When creating XML with etree, it insists on mapping all namespaces.
		You might as well make your XML readable by giving it something to go
		on."""
		#not supported in cElementTree
		#ET._namespace_map[key] = value
		pass

	def waitfor(self, xml, timeout=60):
		"""waitfor(xmlmask, timeout):
		Waits for and returns xml mask matchup. If used in handler, must be
		threaded."""
		# I'm not happy with the way this works
		xmlobj = ET.XML(xml)
		with self.lock:
			self.waitingxml[xmlobj] = Queue.Queue()
		self.add_handler(xmlobj, None, True)
		result = self.waitingxml[xml].get(True, timeout)
		del self.waitingxml[xml]
		return result

	def process_nanny(self):
		self.nanny_queue = Queue.Queue()
		exit_code = 1
		reconnected = False
		while exit_code:
			thread.start_new(self._process, tuple())
			if reconnected:
				self.post_reconnect()
			exit_code = self.nanny_queue.get()
			if exit_code == 1:
				exit_code = self.reconnect()
				reconnected = True
			elif exit_code == 2:
				self._send(self.streamheader)
		logging.debug("Setting connected to False in nanny")
		self.connected = False

	def process(self):
		"""Starts processing incoming stream."""
		if self.connected:
			if not self.listener: #if we're the client
				thread.start_new(self.process_nanny, tuple())
			else:
				thread.start_new(self._process, tuple())
			return True

	def _process(self):
		"""_process is normally called as a new thread from process(). Iterates
		through XML elements and sends them to handlers."""
		with self.lock:
			self.file = filesocket(self.socket)
		try:
			self._doProcess()
			if self.nanny_queue:
				self.nanny_queue.put(0)
		except ExpatError, (text):
			logging.log(logging.ERROR, "disconnected due to expat error: %s" % text)
			if self.nanny_queue:
				self.nanny_queue.put(1)
		except SyntaxError, (strerror):
			if not str(strerror).startswith("no element found"): #ignore a stream that gets closed with nothing having been sent
				logging.log(logging.ERROR, "ElementTree raised SyntaxError.")
				logging.log(logging.DEBUG, traceback.format_exc())
			if self.nanny_queue:
				self.nanny_queue.put(1)
		except socket.error, (errno, strerror):
			logging.log(logging.DEBUG, "Disconnected due to socket error #%s: %s" % (errno, strerror))
			if self.nanny_queue:
				self.nanny_queue.put(1)
		except TypeError:
			logging.log(logging.ERROR, traceback.format_exc())
			if self.nanny_queue:
				self.nanny_queue.put(1)
		except CleanDisconnect:
			logging.log(logging.DEBUG, "Disconnected cleanly.")
			self.disconnect(init=False, close=True)
			if self.nanny_queue:
				self.nanny_queue.put(1)
		except TLSAbruptCloseError:
			logging.log(logging.ERROR, "Disconnected due to TLS being closed.")
			if self.nanny_queue:
				self.nanny_queue.put(1)
		except TLSAlert:
			logging.log(logging.ERROR, "Disconnected due to TLS Alert.")
			logging.log(logging.DEBUG, traceback.format_exc())
			if self.nanny_queue:
				self.nanny_queue.put(1)
		except TLSAuthenticationError:
			logging.error("TLS could not authenticate.")
			self.disconnect(init=False,close=False)
			if self.nanny_queue:
				self.nanny_queue.put(0)
		except RestartStream:
			if self.nanny_queue:
				self.nanny_queue.put(2)
		except:
			logging.error(traceback.format_exc())
			if self.nanny_queue:
				self.nanny_queue.put(0)

	def _doProcess(self):
		"""Actual process() code, called by _process(), which is mostly exception handling."""
		# this is kind of messy.  How can we clean it up?
		edepth = 0
		root = None
		for (event, xmlobj) in ET.iterparse(self.file, ("start", "end")):
			if edepth == 0 and xmlobj.tag.split('}', 1)[-1] == self.basetag:
				if event == 'start':
					root = xmlobj
					thread.start_new(self._start_stream, (xmlobj.__copy__(), ))
			if event == 'end':
				edepth += -1
				if edepth == 0 and event == 'end':
					self._end_stream(xmlobj)
				elif edepth == 1:
					for handler in self.recv_handler:
						if self.maskcmp(xmlobj, handler[0], True): #if handler match
							result = None
							if self.waitingxml.has_key(handler[0]): # if something is waiting on this, then put it in the queue.
								self.waitingxml[handler[0]].put(xmlobj)
							else:
								if handler[3]: # if threaded, then thread
									result = thread.start_new(handler[1], (xmlobj.__copy__(), ))
								else:
									result = apply(handler[1], (xmlobj, ))
								if result == 'break':
									break
							if handler[4] and result: #if filter
								xmlobj = result
							if handler[2]: # if disposable then dispose
								self.recv_handler.pop(self.recv_handler.index(handler))
					if root:
						root.clear()
			if event == 'start':
				edepth += 1

	def _start_stream(self, xmlobj):
		"""automatically called on start of stream"""
		with self.lock:
			self.basens = xmlobj.tag[1:].split('}')[0]
			self.gotstart = True
		if self.listener: 
			#listeners respond to streams, they don't sart them while clients are the opposite
			self._send(self.streamheader)
		for handler in self.start_handler:
			thread.start_new(handler, (xmlobj, ))

	def _end_stream(self, xmlobj):
		"""automatically called on end of stream"""
		for handler in self.end_handler:
			apply(handler, (xmlobj, ))
		raise CleanDisconnect

	def send(self, xml, waitxml=None, timeout=60, ignorefail=False):
		"""send(xml, xmlmask, timeout, ignorefail):
		Sends XML.  If xmlmask is specified, halts execution until match is
		found or timeout (in seconds) is reached. If ignorefail, sending 
		failures won't be logged."""
		if not hasattr(xml, 'tag'):
			xml = ET.XML(xml)
		# send handler
		for handler in self.send_handler:
			if self.maskcmp(xml, handler[0], True): #if handler match
				if handler[3]: # if threaded, then thread
					result = thread.start_new(handler[1], (xml.__copy__(), ))
				else:
					result = apply(handler[1], (xml, ))
				if result == 'break':
					break
				if handler[4] and result: #if filter
					xml = result
				if handler[2]: # if disposable then dispose
					self.send_handler.pop(self.send_handler.index(handler))
		# done handling
		xml = self.tostring(xml, self.default_ns)
		xml = xml.encode('utf-8')
		if hasattr(waitxml, 'tag'):
			waitxml = self.tostring(waitxml)
		timelimit = time.time() + 10.0
		while not self.gotstart and time.time() < timelimit:
			time.sleep(0.1)
		if not self.gotstart:
			logging.log(logging.ERROR, "Could not send.")
		else:
			return self._send(xml, waitxml, timeout, ignorefail)

	def _send(self, xml, waitxml=None, timeout=60, ignorefail=False):
		"""send(xml, xmlmask):
		Sends XML.  If xmlmask is specified, halts execution until match is
		found or timeout reached."""
		# I'm not necessarily happy with how waiting works.
		# I'm especially not happy with it being initiated two different ways
		# in the same class.
		logging.log(logging.COMM, "SEND: %s" % xml)
		if waitxml:
			xmlobj = ET.XML(waitxml)
			with self.lock:
				self.waitingxml[xmlobj] = Queue.Queue()
			self.add_handler(xmlobj, None, True)
		try:
			if "%s" % type(xml) == "<type 'unicode'>":
				xml = xml.encode('utf-8')
			self.socket.send(xml)
		except socket.error,  (errno, strerror):
			if not ignorefail:
				logging.log(logging.WARNING, "Unable to send with error #%s: %s\nWill reconnect." % (errno, strerror))
				self.disconnect(init=False, close=True)
		except ValueError:
			traceback.print_exc()
			if not ignorefail:
				logging.log(logging.WARNING, "Unable to send due to ValueError.")
				self.disconnect(init=False, close=True)
		if waitxml:
			try:
				return self.waitingxml[xmlobj].get(True, timeout)
			except Queue.Empty:
				return False
