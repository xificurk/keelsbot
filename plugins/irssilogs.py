# -*- coding: utf-8 -*-
"""
    plugins/irssilogs.py - A plugin for logging MUC traffice in an irssi style.
    Copyright (C) 2008 Kevin Smith
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
import re

class irssilogfile(object):
    """ Handle writing to a single irssi log file.
    """
    def __init__(self, muc, fileName):
        """ Create a logfile handler for a given muc and file.
        """
        self.muc = muc
        self.fileName = fileName
        self.logfile = file(self.fileName, 'a')
        line = u"--- Začátek logování"
        self.appendLogLine(line)
    
    def datetimeToTimestamp(self, dt):
        """ Convert a datetime to hh:mm
        """
        return "%02d:%02d:%02d" % (dt.hour, dt.minute, dt.second)
        
    def logPresence(self, presence):
        """ Log the presence to the file.
            Formats:
            join = '20:06:07 -!- Nick vstoupi'
            quit = '19:07:08 -!- Nick odešel [status]'
        """
        values = {}
        values['nick'] = presence['nick']
        values['reason'] = presence.get('status', "")
        values['time'] = self.datetimeToTimestamp(presence['dateTime'])
        if presence.get('type', None) == 'unavailable':
            line = u'%(time)s -!- %(nick)s odešel [%(reason)s]'
        else:
            line = u'%(time)s -!- %(nick)s vstoupil'

        self.appendLogLine(line % values)
        
    def logMessage(self, message):
        """ Log the message to the file.
            Formats:
            message = '09:43:42 <Nick> messagebody'
            action  = '10:45:42  * Nick actionbodies'
            topic   = '18:38:42 -!- Nick změnil téma na: New Topic'
        """
        values = {}
        values['nick'] = message['name']
        values['time'] = self.datetimeToTimestamp(message['dateTime'])
        values['body'] = message['message']
        action = False
        topic = False
        system = False
        if values['body'][:4] == '/me ':
            action = True
            values['body'] = values['body'][4:]
        if message['name'] == '':
            system = True
        match = re.match("^(.*) has set the subject to: (.*)", message["message"])
	if match:
	    topic = True
	    values["body"] = match.group(2)
	    values["nick"] = match.group(1)
        elif message["subject"] != "":
            topic = True
            values["body"] = message["subject"]

        if topic:
            line = u"%(time)s -!- %(nick)s nastavil téma na: %(body)s"
        elif system:
            line = u"%(time)s -!- %(body)s"
        elif action:
            line = u"%(time)s  * %(nick)s %(body)s"
        else:
            line = u"%(time)s <%(nick)s> %(body)s"

        self.appendLogLine(line % values)
        
    def logDateChange(self, newDate):
        """ Log a date change.
            Format:
            --- Day changed Thu Aug 16 2007
        """
        values = {}
        values['dayOfWeek'] = [u'Pondělí', u'Úterý', u'Středa', u'Čtvrtek', u'Pátek', u'Sobota', u'Neděle'][newDate.weekday()]
        values['day'] = newDate.day
        values['monthName'] = [u'ledna', u'února', u'března', u'dubna', u'května', u'června', u'července', u'srpna', u'září', u'října', u'listopadu', u'prosince'][newDate.month - 1]
        values['year'] = newDate.year
        line = u"--- %(dayOfWeek)s %(day)s. %(monthName)s %(year)s"
        self.appendLogLine(line % values)
        
    def appendLogLine(self, line):
        """ Append the line to the log
        """
        line = line + "\n"
        if type(line) is unicode:
            line = line.encode('utf-8')
        self.logfile.write(line)
        self.logfile.flush()



class irssilogs(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = u"'Irssilogs' slouží pro logování dění v MUCu.\nAutoři: Kevin Smith, Petr Morávek"
        self.bot.add_event_handler("groupchat_presence", self.handle_groupchat_presence, threaded=True)
        self.bot.add_event_handler("groupchat_message", self.handle_groupchat_message, threaded=True)
        self.bot.add_handler("<message xmlns='jabber:client' type='groupchat'><subject/></message>", self.handle_groupchat_topic)
        self.roomLogFiles = {}
        self.roomMembers = {}
        logs = self.config.findall('log')
        self.lastdate = datetime.datetime.now()
        if logs:
            for log in logs:
                room = log.attrib['room']
                fileName = log.attrib['file']
                self.roomLogFiles[room] = irssilogfile(room, fileName)
                self.roomMembers[room] = []
                logging.info("irssilogs.py script logging %s to %s." % (room, fileName))

    def check_for_date_change(self, date):
        if date.day != self.lastdate.day:
            for log in self.roomLogFiles.values():
                self.lastdate = date
                log.logDateChange(date)

    def handle_groupchat_presence(self, presence):
        """ Monitor MUC presences.
        """
        presence['dateTime'] = datetime.datetime.now()
        self.check_for_date_change(presence['dateTime'])
        if presence['room'] in self.roomLogFiles.keys():
            if presence.get('type', None) == 'unavailable' or presence['nick'] not in self.roomMembers[presence['room']]:
                self.roomLogFiles[presence['room']].logPresence(presence)
                if presence.get('type', None) == 'unavailable':
                    if presence['nick'] in self.roomMembers[presence['room']]:
                        self.roomMembers[presence['room']].remove(presence['nick'])
                else:
                    self.roomMembers[presence['room']].append(presence['nick'])

    def handle_groupchat_message(self, message):
        """ Monitor MUC messages.
        """
        message['dateTime'] = datetime.datetime.now()
        self.check_for_date_change(message['dateTime'])
        if message['room'] in self.roomLogFiles.keys():
            self.roomLogFiles[message['room']].logMessage(message)

    def handle_groupchat_topic(self, xml):
        """ Handle a message event without body element in a muc.
        """
        message = {}
        message["message"] = xml.find("{jabber:client}body")
        if message["message"] is None:
            message["message"] = ""
            message['dateTime'] = datetime.datetime.now()
            self.check_for_date_change(message['dateTime'])

            mfrom = xml.attrib['from']
            message["room"] = self.bot.getjidbare(mfrom)
            if message['room'] in self.roomLogFiles.keys():
                message["subject"] = xml.find("{jabber:client}subject").text
                message["name"] = self.bot.getjidresource(mfrom)
                message["type"] = xml.attrib.get('type', 'normal')
                self.roomLogFiles[message["room"]].logMessage(message)

    def shutDown(self):
        self.bot.del_event_handler("groupchat_presence", self.handle_groupchat_presence, threaded=True)
        self.bot.del_event_handler("groupchat_message", self.handle_groupchat_message, threaded=True)
	self.bot.del_handler("<message xmlns='jabber:client' type='groupchat'><subject/></message>", self.handle_groupchat_topic)
