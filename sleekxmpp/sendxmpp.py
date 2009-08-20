#!/usr/bin/env python2.5
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
import sys

def sendmessage(event):
	global con, target, body, subject, recipient
	global mtype
	for target in recipient:
		con.sendMessage(target, body, msubject=subject, mtype=mtype)
	con.disconnect()


if __name__ == '__main__':
	#parse command line arguements
	optp = OptionParser()
	optp.add_option('-q','--quiet', help='set logging to ERROR', action='store_const', dest='loglevel', const=logging.ERROR, default=logging.INFO)
	optp.add_option('-d','--debug', help='set logging to DEBUG', action='store_const', dest='loglevel', const=logging.DEBUG, default=logging.INFO)
	optp.add_option('-v','--verbose', help='set logging to COMM', action='store_const', dest='loglevel', const=5, default=logging.INFO)
	optp.add_option("-c","--config", dest="configfile", default="config.xml", help="set config file to use")
	optp.add_option("-m","--message", dest="body", default=None)
	optp.add_option("-s","--subject", dest="subject", default=None)
	optp.add_option("-r","--recipient", dest="recipient", default=None)
	optp.add_option("-t","--type", dest="mtype", default='chat', type="choice", choices=['chat', 'normal', 'headline', 'groupchat'])
	opts,args = optp.parse_args()
	
	body = opts.body
	recipient = opts.recipient.split(",")
	subject = opts.subject
	mtype = opts.mtype
	
	if body == None:
	    print "Must specify a message"
	    sys.exit()
	    
	if recipient == None:
	    print "Must specify a recipient"
	    sys.exit()
	
	logging.basicConfig(level=opts.loglevel, format='%(levelname)-8s %(message)s')

	#load xml config
	logging.info("Loading config file: %s" % opts.configfile)
	config = ET.parse(os.path.expanduser(opts.configfile)).find('auth')
	
	#init
	logging.info("Logging in as %s" % config.attrib['jid'])
	
	con = sleekxmpp.xmppclient(config.attrib['jid'], config.attrib['pass'], ssl=True)
	con.add_event_handler('session_start', sendmessage)
	if not config.get('server', None):
		# we don't know the server, but the lib can probably figure it out
		con.connect() 
	else:
		con.connect((config.attrib['server'], 5222))
	con.process()
	# sendmessage will automatically be called when logged in at this point
	while con.connected:
		time.sleep(1)
