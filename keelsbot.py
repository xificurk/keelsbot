#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    keelsbot.py - KeelsBot class. 
    Copyright (C) 2007, 2008 Nathan Fritz
    Copyright (C) 2007, 2008 Kevin Smith
    Copyright (C) 2008-2010 Petr Morávek

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

__version__ = "0.3"


from imp import reload
import logging
from optparse import IndentedHelpFormatter
from optparse import OptionParser
import os.path
import platform
import re
import sys
from time import sleep
from xml.etree import cElementTree as ET

import libs.console as console
from libs.versioning import VersionInfo

import plugins
import sleekxmpp
from store import store


class keelsbot(sleekxmpp.ClientXMPP):
    def __init__(self, configFile):
        self.log = logging.getLogger("keelsbot")
        self.cmdPrefix = "!"

        self.clearCommands()
        self.plugin_whitelist = []
        self.plugin_config = {}

        self.configFile = configFile
        self.loadConfig(configFile)

        auth = self.botconfig.find("auth")
        self.log.info("Logging in as {0}".format(auth.attrib["jid"]))
        sleekxmpp.ClientXMPP.__init__(self, auth.attrib["jid"], auth.attrib["pass"], ssl=False, plugin_config=self.plugin_config, plugin_whitelist=self.plugin_whitelist)

        self.add_event_handler("session_start", self.start, threaded=True)
        self.add_event_handler("message", self.handleMessageEvent, threaded=True)
        self.rooms = {}
        self.botPlugin = {}
        self.register_plugins()
        self.registerBotPlugins()
        self.registerCommands()


    def clearCommands(self):
        self.commands = {}
        self.help = {}


    def loadConfig(self, configFile):
        """ Load config file.
        """
        self.botconfig = ET.parse(configFile)
        self.configSleekPlugins()
        self.configIdentification()
        self.configStorage()
        self.configAcl()


    def configSleekPlugins(self):
        """ Configure Sleek plugins.
        """
        for plugin in self.botconfig.findall("/sleek/plugin"):
            if "name" not in plugin.keys():
                self.log.error("Ignoring unamed SleekXMPP plugin.")
                continue
            self.log.debug("Registering")
            self.plugin_whitelist.append(plugin.get("name"))
            conf = plugin.find("config")
            if conf is not None:
                self.plugin_config[plugin.get("name")] = conf.attrib


    def configIdentification(self):
        """ Configure identification of the bot.
        """
        if "xep_0092" in self.plugin_whitelist:
            if "xep_0092" not in self.plugin_config:
                self.plugin_config["xep_0092"] = {}
            conf = self.plugin_config["xep_0092"]
            if "name" not in conf:
                conf["name"] = "KeelsBot"
            if "version" not in conf:
                conf["version"] = __version__


    def configStorage(self):
        """ Configure persistent storage.
        """
        storageXml = self.botconfig.find("/storage")
        if storageXml is not None:
            self.store = store(storageXml.attrib["file"])
        else:
            self.log.warn("No storage element found in config file - proceeding with no persistent storage, plugin behaviour may be undefined.")


    def configAcl(self):
        """ Configure ACLs.
        """
        # Min access level
        accessLevel = self.botconfig.find("/access-level")
        if accessLevel is not None:
            self.minAccessLevel = max(int(accessLevel.get("min", 0)), 0)
        else:
            self.minAccessLevel = 0

        # User groups
        self.acl = {}
        groups = self.botconfig.findall("/users/group")
        if len(groups) > 0:
            for group in groups:
                level = int(group.get("level", 0))
                name = group.get("name", "group-{0}".format(level))
                if name not in self.acl:
                    self.log.debug("Adding user group '{0}' with level {1}.".format(name, level))
                    self.acl[name] = {"level":level, "users":[]}
                else:
                    self.log.error("User group name collision '{0}'.".format(name))
                    continue
                userJids = group.findall("jid")
                if len(userJids) > 0:
                    for jid in userJids:
                        self.log.debug("Adding user {0} to group '{1}'.".format(jid.text, name))
                        self.acl[name]["users"].append(jid.text)


    def registerBotPlugins(self):
        """ Register all bot plugins.
        """
        plugins = self.botconfig.findall("/plugins/plugin")
        if len(plugins) > 0:
            for plugin in plugins:
                name = plugin.attrib["name"]
                self.log.info("Loading plugin {0}.".format(name))
                loaded = self.registerBotPlugin(name, plugin.find("config"))
                if not loaded:
                    self.log.error("Loading plugin {0} FAILED.".format(name))


    def registerBotPlugin(self, name, config):
        """ Register a bot plugin - name is the file and class name,
        and config is an xml element passed to the plugin. Will reload the plugin module,
        so previously loaded plugins can be updated.
        """
        if name in globals()["plugins"].__dict__:
            reload(globals()["plugins"].__dict__[name])
        else:
            __import__("{0}.{1}".format(globals()["plugins"].__name__, name))

        plugin = getattr(globals()["plugins"].__dict__[name], name)

        if hasattr(plugin, "sleekDependencies"):
            for sleekDep in getattr(plugin, "sleekDependencies"):
                if sleekDep not in self.plugin:
                    self.log.warn("Bot plugin '{0}' needs sleekXMPP plugin '{1}'.".format(name, sleekDep))
                    return False

        self.botPlugin[name] = plugin(self, config)
        return True


    def deregisterBotPlugins(self):
        """ Unregister all loaded bot plugins.
        """
        for plugin in list(self.botPlugin.keys()):
            self.deregisterBotPlugin(plugin)


    def deregisterBotPlugin(self, name):
        """ Unregister a bot plugin.
        """
        self.log.info("Unloading plugin {0}.".format(name))
        if hasattr(self.botPlugin[name], "shutDown"):
            self.log.debug("Plugin has a shutDown() method, so calling that.")
            self.botPlugin[name].shutDown()
        del self.botPlugin[name]


    def registerCommands(self):
        """ Register all ad-hoc commands with SleekXMPP.
        """
        if "xep_0004" not in self.plugin or "xep_0050" not in self.plugin:
            self.log.warn("Ad-hoc commands disabled.")
            return

        aboutform = self.plugin["xep_0004"].makeForm("form", "O KeelsBotovi")
        aboutform.addField("about", "fixed", value="KeelsBot je upravenou verzí SleekBota, kterou napsal Petr Morávek.\nKeelsBot těží z kódu projektu SleekBot, jehož autory jsou Nathan Fritz a Kevin Smith.\nPro komunikaci používá knihovnu SleekXMPP, jejímž autorem je taktéž Nathan Fritz.\nhttp://github.com/xificurk/KeelsBot")
        self.plugin["xep_0050"].addCommand("about", "O KeelsBotovi", aboutform)

        pluginform = self.plugin["xep_0004"].makeForm("form", "Pluginy")
        plugins = pluginform.addField("plugin", "list-single", "Pluginy")
        for name in self.botPlugin:
            plugins.addOption(name, name)
        commands = pluginform.addField("option", "list-single", "Příkazy")
        commands.addOption("about", "O pluginu")
        self.plugin["xep_0050"].addCommand("plugins", "Pluginy", pluginform, self.pluginCommandForm, True)


    def pluginCommandForm(self, form, sessid):
        """ Take appropriate action when a plugin ad-hoc request is received.
        """
        value = form.getValues()
        option = value["option"]
        plugin = value["plugin"]
        if option == "about":
            aboutform = self.plugin["xep_0004"].makeForm("form", "O pluginu")
            aboutform.addField("about", "fixed", value=self.botPlugin[plugin].about)
            return aboutform, None, False


    def getCommandAccessLevel(self, command):
        """ Determine required access level for the command.
            Override this to get better access control.
        """
        level = 0
        levelXml = self.botconfig.findall("/plugins/plugin/acl/{0}".format(command))
        if len(levelXml) > 0:
            level = int(levelXml[0].get("level", 0))
        self.log.debug("Command '{0}' has access level {1}.".format(command, level))
        return level


    def getAccessLevel(self, event):
        """ Returns access level of the sender of the event (negative value means bot should ignore this).
            Override this to get better access control.
        """
        if isinstance(event, sleekxmpp.stanza.message.Message):
            # Ignore errors and headlines
            if event["type"] in ("error", "headline"):
                return -666
            elif event["type"] == "groupchat":
                if event["from"].full == event["mucroom"] or event["mucroom"] not in self.rooms or self.rooms[event["mucroom"]] == event["mucnick"]:
                    #system, error, or own message
                    return -666

        level = 0
        jid = self.getRealJid(event["from"])
        if jid is not None:
            jid = jid.bare

            for group in self.acl:
                if jid in self.acl[group]["users"]:
                    if self.acl[group]["level"] < 0:
                        level = min(level, self.acl[group]["level"])
                    else:
                        level = max(level, self.acl[group]["level"])

        self.log.debug("'{0}' has accesslevel {1}.".format(jid, level))
        return level



    def getRealJid(self, jid):
        """ Returns the 'real' jid.
            If the jid isn't in a muc, it is returned.
            If the jid is in a muc and the true jid is known, that is returned.
            If the jid is in a muc and the true jid isn't known, None is returned.
        """
        if jid.bare in self.rooms:
            self.log.debug("Checking real jid for {0}.".format(jid))
            return self.plugin["xep_0045"].getJidProperty(jid.bare, jid.resource, "jid")
        else:
            return jid


    def joinRooms(self):
        """ Join MUC rooms
        """
        self.log.info("Re-syncing with required channels.")

        newRooms = {}
        for plugin in self.botconfig.findall("/sleek/plugin"):
            if plugin.get("name") == "xep_0045":
                for room in plugin.findall("muc"):
                    newRooms[room.attrib["room"]] = room.attrib["nick"]

        for room in self.rooms:
            if room not in newRooms.keys():
                self.log.info("Leaving room {0}.".format(room))
                self.plugin["xep_0045"].leaveMUC(room, self.rooms[room])
                del self.rooms[room]
        for room in newRooms:
            if room not in self.rooms.keys():
                self.rooms[room] = newRooms[room]
                self.log.info("Joining room {0} as {1}.".format(room, newRooms[room]))
                self.plugin["xep_0045"].joinMUC(room, newRooms[room])


    def connect(self):
        auth = self.botconfig.find("auth")
        if auth.get("server", None) is None:
            # we don't know the server, but the lib can probably figure it out
            return sleekxmpp.ClientXMPP.connect(self)
        else:
            return sleekxmpp.ClientXMPP.connect(self, (auth.attrib["server"], 5222))


    def start(self, event):
        """ Start the bot
        """
        self.getRoster()
        self.sendPresence(ppriority=self.botconfig.find("/auth").get("priority", "1"))
        self.joinRooms()


    def rehash(self):
        """ Re-reads the config file, making appropriate runtime changes.
            Causes all plugins to be reloaded (or unloaded). The XMPP stream, and
            channels will not be disconnected.
        """
        self.log.warn("Deregistering bot plugins for rehash.")
        del globals()["plugins"]
        globals()["plugins"] = __import__("plugins")
        self.clearCommands()
        self.deregisterBotPlugins()

        self.log.info("Reloading config file.")
        self.loadConfig(self.configFile)

        self.registerBotPlugins()
        self.joinRooms()


    def restart(self):
        """ Completely restart the bot.
        """
        global shouldRestart
        shouldRestart = True
        self.log.warn("Restarting bot.")
        self.die()


    def die(self):
        """ Shutdown the bot.
        """
        self.deregisterBotPlugins()
        self.rooms = {}
        self.log.warn("Disconnecting bot.")
        self.disconnect()


    def event(self, name, eventdata={}):
        """ Called on an event - just log it and pass down
        """
        self.log.debug("EVENT: {0}".format(name))
        sleekxmpp.basexmpp.event(self, name, eventdata)


    def handleMessageEvent(self, msg):
        """ Parse message event and run the command
        """
        self.log.debug(msg)
        level = self.getAccessLevel(msg)
        self.log.debug("User lvl: {0}, MinAclLevel: {1}".format(level, self.minAccessLevel))
        if level < self.minAccessLevel or level < 0:
            # Ignore the message
            return

        message = msg["body"]
        if message.startswith(self.cmdPrefix):
            # Remove cmdPrefix from message
            message = message[len(self.cmdPrefix):]

            # Get command name
            command = message.split("\n", 1)[0].split(" ", 1)[0]
            if len(command) == 0:
                # No command name -> return
                return

            if command in self.commands and self.commands[command]["level"] <= level:
                # Parse arguments
                args = message[len(command):]
                if args.startswith(" "):
                    args = args[1:]
                self.log.debug("Command '{0}' with args '{1}'".format(command, args))

                response = self.commands[command]["pointer"](command, args, msg)
                if response is not None and response != "":
                    if msg["type"] == "groupchat":
                        self.sendMessage(msg["mucroom"], "{0}: {1}".format(msg["mucnick"], response), mtype="groupchat")
                    else:
                        self.sendMessage(msg["from"].full, response, mtype=msg["type"])


    def addHelp(self, topic, title=None, body=None, usage=None):
        """ Add help text
        """
        self.help[topic] = (title, body, usage)


    def addCommand(self, command, pointer, helpTitle=None, helpBody=None, helpUsage=None):
        """ Add command with (optionally) help topic
        """
        self.addHelp(command, helpTitle, helpBody, helpUsage)
        level = self.getCommandAccessLevel(command)
        self.commands[command] = {"pointer":pointer, "level":level}



if __name__ == "__main__":
    class sleekxmppLogFilter(logging.Filter):
        def __init__(self):
            logging.Filter.__init__(self)

        def filter(self, record):
            record.name = "SleekXMPP"
            record.levelno = int(record.levelno/10)
            return logging.getLogger("").getEffectiveLevel() <= record.levelno

    # Setup console output logging
    coloredLog = console.ColorLogging(fmt="%(asctime)s %(levelname)-8s %(name)s >> %(message)s", datefmt="%Y-%m-%d %X")
    rootlog = logging.getLogger("")
    rootlog.addHandler(coloredLog)
    rootlog.addFilter(sleekxmppLogFilter())
    rootlog.setLevel(logging.WARN)

    # Parse command line arguements
    optp = OptionParser(formatter=IndentedHelpFormatter(max_help_position=40), conflict_handler="resolve", version="%prog "+__version__)
    optp.add_option("-c", "--config", dest="configfile", default="config.xml", help="set config file to use")
    optp.add_option("-n", "--no-color", help="disable usage of colored output", dest="color", action="store_false", default=True)
    optp.add_option("-q", "--quiet", help="set logging to ERROR", dest="loglevel", action="store_const", const=logging.ERROR, default=logging.WARN)
    optp.add_option("-v", "--verbose", help="set logging to INFO", dest="loglevel", action="store_const", const=logging.INFO)
    optp.add_option("-d", "--debug", help="set logging to DEBUG", dest="loglevel", action="store_const", const=logging.DEBUG)
    optp.add_option("-D", "--Debug", help="set logging to ALL", dest="loglevel", action="store_const", const=0)

    opts,args = optp.parse_args()
    rootlog.setLevel(opts.loglevel)
    mainlog = logging.getLogger("main")
    console.useColor = opts.color
    console.changeColor(console.colors["reset"], sys.stdout)
    console.changeColor(console.colors["reset"], sys.stderr)
    print("")
    configFile = os.path.expanduser(opts.configfile)

    # Check requirements
    # NOTE: Ubuntu modifies version string by '+', OMG :-(, so we drop all but numbers and dots
    version = re.sub("[^0-9.]+", "", platform.python_version())
    version = VersionInfo(version)
    minVersion = "3.1"
    if version < minVersion:
        mainlog.critical("You need at least Python {0} to run this script.".format(minVersion))

    global shouldRestart
    shouldRestart = True
    try:
        while shouldRestart:
            shouldRestart = False
            bot = keelsbot(configFile)
            while not bot.connect():
                sleep(10)
            bot.process()
            while bot.run:
                sleep(1)
        raise SystemExit
    except KeyboardInterrupt:
        bot.die()
        sleep(2)
        raise SystemExit
    except Exception as e:
        print(e)
        mainlog.error("Unexpected error... killing the bot.")
        bot.die()
        sleep(2)
        raise SystemExit
