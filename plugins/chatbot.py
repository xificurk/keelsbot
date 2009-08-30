# This Python file uses the following encoding: utf-8
"""
    plugins/chatbot.py - A plugin making a bot chat with users.
    Copyright (C) 2008 Pavel Šimerda
    Copyright (C) 2009 Petr Morávek
    Part of the code was taken from Pavel Šimerda's Arabicus bot under
    CC-attribution license.

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

from xml.etree import ElementTree as ET
import datetime
import time
import logging
import glob
import re
import random
import thread

class Filters(object):
    def __init__(self, bot):
        self.bot = bot

    def common(self, msg, prefix, reply):
        reply = reply.replace('////', "\n")

        if msg['type'] == 'groupchat':
            reply = reply.replace('//BOTNICK//', self.bot.bot.rooms[msg['room']])
            reply = reply.replace('//NICK//', msg['name'])
        elif msg.get('jid', '') in self.bot.rooms:
            reply = reply.replace('//BOTNICK//', self.bot.bot.rooms[msg['jid']])
            reply = reply.replace('//NICK//', msg['resource'])
        return prefix, reply

    def direct(self, msg, prefix, reply):
        if msg['type'] == 'groupchat':
            prefix = "%s: " % msg['name']
        else:
            prefix = ''
        return prefix, reply

    def time(self, msg, prefix, reply):
        now = datetime.datetime.now()
        return prefix, reply.replace('//TIME//', "%d:%.2d" % (now.hour, now.minute))

    def date(self, msg, prefix, reply):
        now = datetime.datetime.now()
        return prefix, reply.replace('//DATE//', "%d. %d." % (now.day, now.month))

class Conversations(object):
    def __init__(self, filenames=[]):
        self.files = []
        self.queries = []
        for filename in filenames:
            self.files.extend(glob.glob(filename))
        for file in sorted(self.files):
            self.load(file)
        logging.debug("%s" % self.queries)

    def load(self, file):
        logging.debug("Loading file %s" % file)
        root = ET.parse(file)

        id_map = {}
        data = {}
        data['queries'] = []
        self.parseQueries(root, data, id_map)
        self.replaceIds(id_map, data['queries'], 'replies')
        self.queries.extend(data['queries'])

    def parseQueries(self, element, context, id_map):
        for query in element.findall('query'):
            try:
                item = dict(query.attrib)
                item['scope'] = item.get('scope', 'direct')
                item['pattern'] = re.compile(item.pop('match'),  re.I | re.U)
                item['replies'] = []
                if 'id' in item:
                    id_map[item['id']] = item
                context['queries'].append(item)
                self.parseReplies(query, item, id_map)
            except re.error, e:
                logging.error('Regular expression error: %s' % repr(query.attrib['match']))

    def parseReplies(self, element, context, id_map):
        for reply in element.findall('reply'):
            item = dict(reply.attrib)
            item['text'] = item.get('text', '')
            item['scope'] = item.get('scope', 'chat')
            item['weight'] = int(item.get('weight', 1))
            item['queries'] = []
            if 'id' in item:
                id_map[item['id']] = item
            context['replies'].append(item)
            self.parseQueries(reply, item, id_map)

    def replaceIds(self, id_map, context, element):
        for item in context:
            if element == 'replies':
                next = 'queries'
            else:
                next = 'replies'
            self.replaceIds(id_map, item[element], next)
            if 'extends' in item and item['extends'] in id_map:
                item[element].extend(id_map[item['extends']][element])
                item.pop('extends')

    def getReply(self, convstate, convstate_sup, query, flags=['chat']):
        logging.debug("Getting reply to '%s'" % query)
        queries = []
        queries += filter(lambda i: i['scope'] in flags, convstate)
        queries += filter(lambda i: i['scope'] in flags, convstate_sup)
        queries += filter(lambda i: i['scope'] in flags, self.queries)
        for item in queries:
            if item['pattern'].search(query):
                reply = self.getRandomReply(item['replies'], flags)
                filters = reply.get('filter', 'common')
                if filters != 'common':
                    filters = "%s common" % filters
                return reply['text'], reply['queries'], filters.split(" ")
        return None, None, None

    def getRandomReply(self, choice, flags=['chat']):
        replies = []
        replies += filter(lambda i: i['scope'] in flags, choice)
        sum = 0
        for item in replies:
            sum = sum + item['weight']

        logging.debug('Random choice from sum %i' % sum)

        select = random.randint(1,sum)
        sum = 0
        for item in replies:
            sum = sum + item['weight']
            if select <= sum:
                return item

class chatbot(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.states_mucs = {}
        self.states_jids = {}
        self.messageBuffer = []
        self.rooms = {}
        self.filters = Filters(self)
        rooms = self.config.findall('muc')
        for room in rooms:
            self.states_mucs[room.get('room')] = {}
            if room.get('disabled', None) == None:
                logging.debug('Starting to chat in room %s' % room.get('room'))
                self.rooms[room.get('room')] = {'chatty':True, 'msgcounter':0}
            else:
                logging.debug('NOT Starting to chat in room %s' % room.get('room'))
                self.rooms[room.get('room')] = {'chatty':False, 'msgcounter':0}
        self.dicts = []
        dicts = self.config.findall('dict')
        for dict in dicts:
            if dict.get('name', None) != None:
                self.dicts.append(dict.get('name', None))
        self.conversations = Conversations(self.dicts)
        self.logPath = None
        debug = self.config.find('debug')
        if debug != None and debug.get('log', None) != None:
            self.logPath = debug.get('log')
        self.about = u"'Chatbot' umožňuje botovi odpovídat na určité zprávy v MUC i PM..\nAutoři: Pavel Šimerda, Petr Morávek"
        self.bot.addCommand('shut', self.handle_shut, u'Vypnout chatbota v MUC', u"Bot přestane odpovídat předdefinovanými odpověďmi v zadaném MUC.", 'shut [MUC]')
        self.bot.addCommand('chat', self.handle_chat, u'Zapnout chatbota v MUC', u"Bot začne odpovídat předdefinovanými odpověďmi v zadaném MUC.", 'chat [MUC]')
        self.bot.addCommand('convreload', self.handle_reload, u'Znovunačtení konverzací', u"Bot znovu naparsuje XMLka s uloženými konverzacemi, aniž by při tom opustil jabber, nebo zapomněl současný stav konverzací.", 'convreload')
        self.bot.add_event_handler("groupchat_message", self.handle_message, threaded=True)
        self.bot.add_event_handler("message", self.handle_message, threaded=True)
        self.running = True
        thread.start_new(self.sender, tuple())

    def sender(self):
        while self.running:
            while len(self.messageBuffer) > 0:
                message = self.messageBuffer.pop(0)
                self.sendResponse(message)
            time.sleep(2)

    def sendResponse(self, msg):
        """ Sends response to the room.
        """
        prefix = msg.get('prefix', '')
        for responseLine in self.parseMultiline(msg['message'], prefix):
            time.sleep(random.randint(min(9,max(2,len(responseLine['reply'])/9)), min(25,max(5,len(responseLine['reply'])/6))))
            if msg['type'] == 'groupchat':
                self.bot.sendMessage("%s" % msg['jid'], "%s%s" % (responseLine['prefix'], responseLine['reply']), mtype='groupchat')
            else:
                self.bot.sendMessage("%s" % msg['jid'], "%s%s" % (responseLine['prefix'], responseLine['reply']), mtype='chat')

    def parseMultiline(self, response, prefix=''):
        """ Parses | out into multiple strings and actions.
        """
        responses = response.split('|')
        for i in range(len(responses)):
            if responses[i][0] == '/':
                responses[i] = {'prefix':'', 'reply':'/me ' + responses[i][1:]}
            else:
                responses[i] = {'prefix':prefix, 'reply':responses[i]}
        return responses

    def shutDown(self):
        self.running = False
        self.bot.del_event_handler("groupchat_message", self.handle_message, threaded=True)
        self.bot.del_event_handler("message", self.handle_message, threaded=True)

    def handle_chat(self, command, args, msg):
        if args == '':
            if msg['type'] == 'groupchat':
                args = msg.get('room', None)
            else:
                args = msg.get('jid', None)

        if self.rooms.get(args, None) == None:
            return u"V místnosti '%s' já vůbec nechatuju ;-)" % args
        else:
            self.rooms[args]['chatty'] = True
            return u'OK, začnu se vykecávat v místnosti %s' % args

    def handle_shut(self, command, args, msg):
        if args == '':
            if msg['type'] == 'groupchat':
                args = msg.get('room', None)
            else:
                args = msg.get('jid', None)

        if self.rooms.get(args, None) == None:
            return u"V místnosti '%s' já vůbec nechatuju ;-)" % args
        else:
            self.rooms[args]['chatty'] = False
            return u'OK, v místnosti %s se už nebudu vykecávat ;-)' % args

    def handle_reload(self, command, args, msg):
        self.conversations = Conversations(self.dicts)
        logging.info('Conversation files reloaded.')
        return u'Tak jsem to znova načetl, šéfiku.'

    def handle_message(self, msg):
        """ Handle message for chatbot
        """
        msgCounter = self.responseInit(msg)
        if msgCounter == False:
            return

        if msg.get('type') == 'groupchat':
            message, flags, convstate, convstate_sup = self.responsePrepareMUC(msg, msgCounter)
        else:
            flags = ['chat', 'direct', 'private']
            if msg['jid'] in self.states_mucs:
                message, convstate, convstate_sup = self.responsePrepareMUCPM(msg)
            else:
                message, convstate = self.responsePreparePM(msg)
                convstate_sup = []

        reply, new_convstate, filters = self.conversations.getReply(convstate, convstate_sup, message, flags)

        self.responseLog(msg, reply)

        if reply != None:
            if msg['type'] == 'groupchat':
                self.states_mucs[msg['room']][msg['name']]['public'] = {'msgTimer':int(time.time()), 'msgCounter':msgCounter, 'state':new_convstate}
                if 'direct' in flags:
                    filters.extend(['direct'])
            elif msg.get('jid', '') in self.rooms:
                self.states_mucs[msg['jid']][msg['resource']]['private'] = {'msgTimer':int(time.time()), 'state':new_convstate}
                filters.extend(['no-direct'])
            else:
                self.states_jids[msg['jid']] = {'msgTimer':int(time.time()), 'state':new_convstate}
                filters.extend(['no-direct'])

        if reply != None and reply != '':
            prefix, reply = self.responseFilters(msg, reply, filters)

            if msg.get('type') == 'groupchat':
                msgType = 'groupchat'
                msgJid = "%s" % msg['room']
            else:
                msgType = 'chat'
                msgJid = "%s/%s" % (msg.get('jid', ''), msg.get('resource', ''))

            self.messageBuffer.append({'message':reply, 'prefix':prefix, 'type':msgType, 'jid':msgJid})

    def responseInit(self, msg):
        """ Should chatbot respond? Return msgCounter
        """
        msgCounter = None
        if msg['type'] == 'groupchat':
            if msg['name'] == "" or self.rooms.get(msg.get('room', ''), None) == None:
                return False
            else:
                self.rooms[msg['room']]['msgcounter'] = self.rooms[msg['room']]['msgcounter']+1
                msgCounter = self.rooms[msg['room']]['msgcounter']

            if self.bot.rooms[msg['room']] == msg['name']:
                return False
            if self.rooms[msg['room']]['chatty'] == False:
                return False

        if msg.get('message', '').startswith(self.bot.cmd_prefix):
            respond = False
            level = self.bot.getAccessLevel(msg)
            if level >= 0:
                if level < self.bot.minAccessLevel:
                    respond = True
                else:
                    command = msg.get('message', '').split("\n",1)[0].split(' ', 1)[0]
                    if len(self.bot.cmd_prefix):
                        command = command.split(self.bot.cmd_prefix, 1)[-1]
                    if command not in self.bot.commands or self.bot.commands[command]['level'] > level:
                        respond = True
            if respond == False:
                return False

        return msgCounter

    def responsePrepareMUC(self, msg, msgCounter):
        """ Parses MUC message
        """
        flags = []
        message = msg['message']

        message = message.replace(self.bot.rooms[msg['room']], '//BOTNICK//')
        match = re.match('^//BOTNICK//[:,>] ?(.*)$', message)
        if match:
            message = match.group(1)
            flags = ['chat', 'direct', 'public']
        else:
            flags = ['chat', 'global', 'public']
        if self.states_mucs[msg['room']].get(msg['name'], None) == None:
            self.states_mucs[msg['room']][msg['name']] = {'private':{}, 'public':{}}
        msgCounter_old = self.states_mucs[msg['room']][msg['name']]['public'].get('msgCounter', None)
        msgTimer_old = self.states_mucs[msg['room']][msg['name']]['public'].get('msgTimer', None)
        convstate = []
        if msgCounter_old != None and (msgCounter - msgCounter_old) <= 30 and msgTimer_old != None and (int(time.time()) - msgTimer_old) <= 2*3600:
            convstate = self.states_mucs[msg['room']][msg['name']]['public'].get('state', [])
        else:
            self.states_mucs[msg['room']][msg['name']]['public']['state'] = []
        convstate_sup = []
        for name in self.states_mucs[msg['room']].keys():
            if name == msg['name']:
                continue
            msgCounter_old = self.states_mucs[msg['room']][name]['public'].get('msgCounter', None)
            msgTimer_old = self.states_mucs[msg['room']][name]['public'].get('msgTimer', None)
            if msgCounter_old != None and (msgCounter - msgCounter_old) <= 5 and msgTimer_old != None and (int(time.time()) - msgTimer_old) <= 1800:
                convstate_sup.extend(self.states_mucs[msg['room']][name]['public'].get('state', []))

        return message, flags, convstate, convstate_sup

    def responsePrepareMUCPM(self, msg):
        """ Parses MUC private message
        """
        message = msg['message']

        if self.states_mucs[msg['jid']].get(msg['resource'], None) == None:
            self.states_mucs[msg['jid']][msg['resource']] = {'private':{}, 'public':{}}
        msgTimer_old = self.states_mucs[msg['jid']][msg['resource']]['private'].get('msgTimer', None)
        convstate = []
        if msgTimer_old != None and (int(time.time()) - msgTimer_old) <= 2*3600:
            convstate = self.states_mucs[msg['jid']][msg['resource']]['private'].get('state', [])
        else:
            self.states_mucs[msg['jid']][msg['resource']]['private']['state'] = []
        convstate_sup = []
        msgTimer_old = self.states_mucs[msg['jid']][msg['resource']]['public'].get('msgTimer', None)
        if msgTimer_old != None and (int(time.time()) - msgTimer_old) <= 1800:
            convstate_sup.extend(self.states_mucs[msg['jid']][msg['resource']]['public'].get('state', []))

        return message, convstate, convstate_sup

    def responsePreparePM(self, msg):
        """ Parses private message
        """
        message = msg['message']

        if self.states_jids.get(msg['jid'], None) == None:
            self.states_jids[msg['jid']] = {}
        msgTimer_old = self.states_jids[msg['jid']].get('msgTimer', None)
        convstate = []
        if msgTimer_old != None and (int(time.time()) - msgTimer_old) <= 2*3600:
            convstate = self.states_jids[msg['jid']].get('state', [])
        else:
            self.states_jids[msg['jid']]['state'] = []

        return message, convstate

    def responseLog(self, msg, reply):
        """ Log response
        """
        if self.logPath != None:
            message = msg['message']
            if msg['type'] == 'groupchat':
                logFile = msg['room']
                message = "%s\t%s" % (msg['name'], message)
            else:
                logFile = "%s---%s" % (msg.get('jid', '').replace("/", "-"), msg.get('resource', '').replace("/", "-"))
            dnf = 'OK'
            if reply == None:
                dnf = 'DNF'
            file('%s/%s.log' % (self.logPath, logFile), 'a').write(('%s\t%s\t%s\n\t\t%s\n' % (datetime.datetime.now(), dnf, message.replace("\n", "||"), reply)).encode('utf-8'))

    def responseFilters(self, msg, reply, filters):
        """ Apply filters
        """
        prefix = ''

        for name in filters:
            if not name.startswith('no-') and not ("no-%s" % name) in filters:
                try:
                    filt = getattr(self.filters, name)
                    prefix, reply = filt(msg, prefix, reply)
                except:
                    logging.error("Filter error: %s" % name)

        return prefix, reply
