#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    keelsbot.py - KeelsBot class. 
    Copyright (C) 2007, 2008 Nathan Fritz
    Copyright (C) 2007, 2008 Kevin Smith
    Copyright (C) 2008, 2009 Petr Morávek

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

from __future__ import with_statement
import logging
import sleekxmpp.sleekxmpp
from basebot import basebot
from store import store
from optparse import OptionParser
from xml.etree import ElementTree as ET
import os
import time
import plugins
import sys

class keelsbot(sleekxmpp.sleekxmpp.xmppclient, basebot):
    def __init__(self, configFile, jid, password, ssl=False, plugin_config = {}):
        self.configFile = configFile
        self.botconfig = self.loadConfig(configFile)
        sleekxmpp.sleekxmpp.xmppclient.__init__(self, jid, password, ssl, plugin_config)
        basebot.__init__(self)
        storageXml = self.botconfig.find('storage')
        if storageXml is not None:
            self.store = store(storageXml.attrib['file'])
        else:
            logging.warning("No storage element found in config file - proceeding with no persistent storage, plugin behaviour may be undefined.")
        accessLevel = self.botconfig.find('access-level')
        if accessLevel is not None:
            self.minAccessLevel = max(int(accessLevel.get('min', 0)),0)
        lang = self.botconfig.find('lang')
        if lang is not None:
            lang = lang.text
        if lang in ['cs']:
            self.lang = lang

        self.parseUserGroups()
        self.rooms = {}
        self.botPlugin = {}
        self.pluginConfig = {}
        self.add_event_handler("session_start", self.start, threaded=True)
        self.register_bot_plugins()
        self.registerCommands()

    def baseTranslations(self):
        self.translations["about"] = {"cs":"O KeelsBotovi"}
        self.translations["about_text"] = {"cs":"KeelsBot je upravenou verzí SleekBota, kterou napsal Petr Morávek.\nKeelsBot těží z kódu projektu SleekBot, jehož autory jsou Nathan Fritz a Kevin Smith.\nPro komunikaci používá knihovnu SleekXMPP, jejímž autorem je taktéž Nathan Fritz.\nhttp://keelsbot.googlecode.com"}
        self.translations["plugins"] = {"cs":"Pluginy"}
        self.translations["commands"] = {"cs":"Příkazy"}
        self.translations["about_plugin"] = {"cs":"O pluginu"}

    def parseUserGroups(self):
        """ Parse user groups for ACLs.
        """
        self.acl = {}
        groups = self.botconfig.findall('users/group')
        if groups:
            for group in groups:
                level = int(group.get('level', 0))
                name = group.get('name', "group-%s" % level)
                if name not in self.acl:
                    self.acl[name] = {'level':level,'users':[]}
                userJids = group.findall('jid')
                if userJids:
                    for jid in userJids:
                        logging.debug("appending %s to %s list" % (jid.text, name))
                        self.acl[name]['users'].append(jid.text)
        logging.debug(self.acl)


    def loadConfig(self, configFile):
        """ Load the specified config. Does not attempt to make changes based upon config.
        """
        return ET.parse(configFile)
    
    def registerCommands(self):
        """ Register all ad-hoc commands with SleekXMPP.
        """
        aboutform = self.plugin['xep_0004'].makeForm('form', self.translate("about"))
        aboutform.addField('about', 'fixed', value=self.translate("about_text"))
        self.plugin['xep_0050'].addCommand('about', self.translate("about"), aboutform)
        pluginform = self.plugin['xep_0004'].makeForm('form', self.translate("plugins"))
        plugins = pluginform.addField('plugin', 'list-single', self.translate("plugins"))
        for key in self.botPlugin:
            plugins.addOption(key, key)
        plugins = pluginform.addField('option', 'list-single', self.translate("commands"))
        plugins.addOption('about', self.translate("about_plugin"))
        self.plugin['xep_0050'].addCommand('plugins', self.translate("plugins"), pluginform, self.form_plugin_command, True)

    def del_event_handler(self, name, pointer, threaded=False, disposable=False):
        with self.lock:
            self.event_handlers[name].pop(self.event_handlers[name].index((pointer, threaded, disposable)))

    def del_handler(self, xmlobj, pointer, disposable=False, threaded=False, filter = False):
        with self.lock:
            self.recv_handler.pop(self.recv_handler.index((xmlobj, pointer, disposable, threaded, filter)))

    def form_plugin_command(self, form, sessid):
        """ Take appropriate action when a plugin ad-hoc request is received.
        """
        value = form.getValues()
        option = value['option']
        plugin = value['plugin']
        if option == 'about':
            aboutform = self.plugin['xep_0004'].makeForm('form', self.translate("about_plugin"))
            aboutform.addField('about', 'fixed', value=self.botPlugin[plugin].about)
            return aboutform, None, False
        elif option == 'config':
            pass

    def register_bot_plugins(self):
        """ Registers all bot plugins required by botconfig.
        """
        plugins = self.botconfig.findall('plugins/bot/plugin')
        if plugins:
            for plugin in plugins:
                logging.info("Loading plugin %s." % (plugin.attrib['name']))
                loaded = self.registerBotPlugin(plugin.attrib['name'], plugin.find('config'))
                if not loaded:
                    logging.info("Loading plugin %s FAILED." % (plugin.attrib['name']))
    
    def deregister_bot_plugins(self):
        """ Unregister all loaded bot plugins.
        """
        for plugin in self.botPlugin.keys():
            self.deregisterBotPlugin(plugin)
    
    def plugin_name_to_module(self, pluginname):
        """ Takes a plugin name, and returns a module name
        """
        #following taken from sleekxmpp.py
        # discover relative "path" to the plugins module from the main app, and import it.
        return "%s.%s" % (globals()['plugins'].__name__, pluginname)
    
    def deregisterBotPlugin(self, pluginName):
        """ Unregisters a bot plugin.
        """
        logging.info("Unloading plugin %s" % pluginName)
        if hasattr(self.botPlugin[pluginName], 'shutDown'):
            logging.debug("Plugin has a shutDown() method, so calling that.")
            self.botPlugin[pluginName].shutDown()
        del self.pluginConfig[pluginName]
        del self.botPlugin[pluginName]
    
    def registerBotPlugin(self, pluginname, config):
        """ Registers a bot plugin pluginname is the file and class name,
        and config is an xml element passed to the plugin. Will reload the plugin module,
        so previously loaded plugins can be updated.
        """
        if pluginname in globals()['plugins'].__dict__:
            reload(globals()['plugins'].__dict__[pluginname])
        else:
            __import__(self.plugin_name_to_module(pluginname))
        self.botPlugin[pluginname] = getattr(globals()['plugins'].__dict__[pluginname], pluginname)(self, config)
        self.pluginConfig[pluginname] = config
        return True
        
    def getRealJid(self, jid):
        """ Returns the 'real' jid.
            If the jid isn't in a muc, it is returned.
            If the jid is in a muc and the true jid is known, that is returned.
            If it's in muc and the true jid isn't known, None is returned.
        """
        bareJid = self.getjidbare(jid)
        nick = self.getjidresource(jid)
        if bareJid in self.plugin['xep_0045'].getJoinedRooms():
            logging.debug("Checking real jid for %s %s (%s)" %(bareJid, nick, jid))
            realJid = self.plugin['xep_0045'].getJidProperty(bareJid, nick, 'jid')
            if realJid:
                return realJid
            else:
                return None
        return jid

    def getAccessLevel(self, event):
        """ Returns access level of the sender of the event (negative value means bot should ignore this).
            Override this to get better access control.
        """
        if event['type'] == 'groupchat':
            if event['name'] == "" or event['room'] not in self.rooms or self.rooms[event['room']] == event['name']:
                #system message
                return -666
            return self.getJidsAccessLevel("%s/%s" % (event['room'], event['name']))
        else:
            if event['jid'] in self['xep_0045'].getJoinedRooms():
                return self.getJidsAccessLevel("%s/%s" % (event['jid'], event['resource']))
            return self.getJidsAccessLevel(event.get('jid', ''))

    def getJidsAccessLevel(self, jid):
        """ Returns access level of the jid (negative value means bot should ignore this).
            Pass in a muc jid if you want, it'll be converted to a real jid if possible
            Accepts 'None' jids (acts as an unknown user).
        """
        level = 0

        jid = self.getRealJid(jid)
        if jid:
            jid = self.getjidbare(jid)

            for group in self.acl:
                if jid in self.acl[group]['users']:
                    if self.acl[group]['level'] < 0:
                        level = min(level, self.acl[group]['level'])
                    else:
                        level = max(level, self.acl[group]['level'])

            logging.debug("%s has accesslevel %d." % (jid, level))
        return level

    def getCommandAccessLevel(self, command):
        """ Determine required access level for the command.
            Override this to get better access control.
        """
        level = 0
        commands = self.botconfig.findall('plugins/bot/plugin/acl/' + command)
        if commands:
            level = int(commands[0].get('level', 0))
        logging.debug("Command %s has access level %d" % (command, level))
        return level
    

    def start(self, event):
        #TODO: make this configurable
        self.requestRoster()
        self.sendPresence(ppriority = self.botconfig.find('auth').get('priority', '1'))
        self.joinRooms()
    
    def rehash(self):
        """ Re-reads the config file, making appropriate runtime changes.
            Causes all plugins to be reloaded (or unloaded). The XMPP stream, and
            channels will not be disconnected.
        """
        logging.info("Deregistering bot plugins for rehash")
        del globals()['plugins']
        globals()['plugins'] = __import__('plugins')
        self.clearCommands()
        self.deregister_bot_plugins()
        logging.info("Reloading config file")
        self.botconfig = self.loadConfig(self.configFile)
        self.register_bot_plugins()
        self.joinRooms()
    
    
    def joinRooms(self):
        logging.info("Re-syncing with required channels")
        newRoomXml = self.botconfig.findall('rooms/muc')
        newRooms = {}
        if newRoomXml:
            for room in newRoomXml:
                newRooms[room.attrib['room']] = room.attrib['nick']
        for room in self.rooms.keys():
            if room not in newRooms.keys():
                logging.info("Parting room %s." % room)
                self.plugin['xep_0045'].leaveMUC(room, self.rooms[room])
                del self.rooms[room]
        for room in newRooms.keys():
            if room not in self.rooms.keys():
                self.rooms[room] = newRooms[room]
                logging.info("Joining room %s as %s." % (room, newRooms[room]))
                self.plugin['xep_0045'].joinMUC(room, newRooms[room])

    def die(self):
        """ Kills the bot.
        """
        self.deregister_bot_plugins()
        self.rooms = {}
        logging.info("Disconnecting bot")
        self.disconnect()

    def restart(self):
        """ Cause the bot to be completely restarted (will reconnect etc.)
        """
        global shouldRestart
        shouldRestart = True
        logging.info("Restarting bot")
        self.die()

if __name__ == '__main__':
    #parse command line arguements
    optp = OptionParser()
    optp.add_option('-q','--quiet', help='set logging to ERROR', action='store_const', dest='loglevel', const=logging.ERROR, default=logging.INFO)
    optp.add_option('-d','--debug', help='set logging to DEBUG', action='store_const', dest='loglevel', const=logging.DEBUG, default=logging.INFO)
    optp.add_option('-v','--verbose', help='set logging to COMM', action='store_const', dest='loglevel', const=5, default=logging.INFO)
    optp.add_option("-c","--config", dest="configfile", default="config.xml", help="set config file to use")
    opts,args = optp.parse_args()
    
    logging.basicConfig(level=opts.loglevel, format='%(levelname)-8s %(message)s')

    global shouldRestart
    shouldRestart = True
    while shouldRestart:
        shouldRestart = False
        #load xml config
        logging.info("Loading config file: %s" % opts.configfile)
        configFile = os.path.expanduser(opts.configfile)
        config = ET.parse(configFile)
        auth = config.find('auth')
        
        clientName = 'KeelsBot'
        clientVersion = '0.1-dev'
        client = config.find('client')
        if client is not None:
            clientName = client.get('name', clientName)
            clientVersion = client.get('version', clientVersion)
            logging.debug('Setting user customized Client ' + clientName + ' ' + clientVersion)
    
        #init
        logging.info("Logging in as %s" % auth.attrib['jid'])
    
        plugin_config = {}
        plugin_config['xep_0092'] = {'name': clientName, 'version': clientVersion}
    
        bot = keelsbot(configFile, auth.attrib['jid'], auth.attrib['pass'], plugin_config=plugin_config)
        
        if not auth.get('server', None):
            # we don't know the server, but the lib can probably figure it out
            bot.connect()
        else:
            bot.connect((auth.attrib['server'], 5222))
        bot.process()
        while bot.connected:
            time.sleep(1)
