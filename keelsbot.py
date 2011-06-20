#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main KeelsBot script.

Classes:
    BaseBot         --- Base class for the XMPP bot.
    KeelsBot        --- KeelsBot main class.
    Help            --- Help item.
    UserConfig      --- User configuration item.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2007, 2008 Nathan Fritz",
                 "Copyright (c) 2007, 2008 Kevin Smith",
                 "Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"

from collections import namedtuple
import gettext as gt
from imp import reload
import logging
from optparse import IndentedHelpFormatter, OptionGroup, OptionParser
import os.path
import sys
from time import sleep
from xml.etree import cElementTree as ET

sys.path.insert(0, os.path.join(sys.path[0], "libs"))

import colterm
import plugins
import sleekxmpp
from sleekxmpp.xmlstream import JID
from storage import Storage
from versioning import python_version

# Global gettext translation for console output etc.
_localedir = os.path.join(os.path.dirname(__file__), "locale")
colterm.init_translation(_localedir)
gt.install("keelsbot", localedir=_localedir, codeset="utf-8", names=("gettext", "ngettext"))


# Logging
log = logging.getLogger("keelsbot")
__ = lambda x: x # Fake gettext function

# Misc data structures
Help = namedtuple("Help", "title body")
UserConfig = namedtuple("UserConfig", "level lang")


class BaseBot(sleekxmpp.ClientXMPP):
    """
    Base class for the XMPP bot.

    Attributes:
        auth            --- Authentication data.
        cmd_prefix      --- Prefix used for commands.
        bot_plugins     --- Bot's plugins.
        store           --- Persistent Storage object.
        permissions     --- Command access levels.
        commands        --- Registered commands.
        help_topics     --- Registered help topics.
        translations    --- Dictionary with gettext translations.
        muc_nicks       --- Dictionary with Nicks in MUCs.
        users           --- Users config dictionary (None key corresponds to default values).

    Methods:
        run                     --- Run the bot (connect and start processing events).
        die                     --- Shutdown the bot.
        handle_session_start    --- Handler for session_start event.
        handle_message          --- Handler for message event.
        sync_rooms              --- Join/leave MUC rooms.
        get_user_config         --- Get UserConfig corresponding to the given JID.
        register_bot_plugin     --- Register and configure a bot plugin.
        deregister_bot_plugins  --- Deregister all registered bot plugins.
        deregister_bot_plugin   --- Deregister a bot plugins.
        add_help_topic          --- Add help topic.
        add_command             --- Add command and corresponding help topic.
        get_translations        --- Get gettext translations instance for a specified language.
        gettext                 --- Call gettext method on the translations instance of a specified language.
        ngettext                --- Call ngettext method on the translations instance of a specified language.

    """

    cmd_prefix = "!"
    bot_plugins = {}
    store = None
    commands = {}
    help_topics = {}
    translations = {}
    muc_nicks = {}
    users = {}

    def __init__(self, auth):
        """
        Arguments:
            auth            --- Authentication data.

        """
        self.auth = auth
        log.info(_("Logging in as {!r}.").format(auth["jid"]))
        sleekxmpp.ClientXMPP.__init__(self, auth["jid"], auth["password"])

        self.add_event_handler("session_start", self.handle_session_start, threaded=True)
        self.add_event_handler("message", self.handle_message, threaded=True)

    def run(self):
        """
        Run the bot (connect and start processing events).

        """
        if "server" in self.auth and "port" in self.auth:
            self.connect(tuple(self.auth["server"], self.auth["port"]))
        else:
            self.connect()
        bot.process(False)

    def die(self):
        """
        Shutdown the bot.

        """
        self.deregister_bot_plugins()
        self.muc_nicks = {}
        log.warn(_("Disconnecting the bot."))
        self.disconnect()

    def event(self, name, data={}, direct=False):
        """ Called on an event - just log it and pass down """
        log.debug(_("EVENT: {}").format(name))
        sleekxmpp.ClientXMPP.event(self, name, data=data, direct=direct)

    def handle_session_start(self, data):
        """
        Handler for session_start event.

        Arguments:
            data        --- Event data.

        """
        self.get_roster()
        self.send_presence(ppriority=self.auth.get("priority", "1"))
        self.sync_rooms()

    def handle_message(self, msg):
        """
        Handler for message event.

        Arguments:
            msg         --- Message stanza.

        """
        # Ignore errors and headlines
        if msg["type"] in ("", "error", "headline"):
            return
        # Ignore MUC system, error and own messages
        if msg["type"] == "groupchat" and (msg["from"].full == msg["mucroom"] or msg["mucroom"] not in self.muc_nicks or self.muc_nicks[msg["mucroom"]] == msg["mucnick"]):
            return

        user_config = self.get_user_config(msg["from"])
        if user_config.level < 0:
            # Ignore the message
            return

        message = msg["body"]
        if message.startswith(self.cmd_prefix):
            # Remove cmd_prefix from message
            message = message[len(self.cmd_prefix):]

            # Get command name
            command = message.split("\n", 1)[0].split(" ", 1)[0]
            if len(command) == 0:
                # No command name, ignore
                return

            if command in self.commands and self.permissions["command:"+command] <= user_config.level:
                # Parse arguments
                args = message[len(command):]
                if args.startswith(" "):
                    args = args[1:]
                log.debug(_("Command {!r} with args {!r}").format(command, args))

                response = self.commands[command](command, args, msg, user_config)
                if response is not None and response != "":
                    if msg["type"] == "groupchat":
                        response = "{}: {}".format(msg["mucnick"], response)
                    msg.reply(response).send()

    def sync_rooms(self):
        """
            Join/leave MUC rooms.

        """
        if "xep_0045" not in self.plugin:
            return
        log.info(_("Re-syncing with required MUC rooms."))
        plugin = self.plugin["xep_0045"]
        for room in plugin.rooms:
            nick = plugin.ourNicks.get(room)
            if room not in self.muc_nicks or nick != self.muc_nicks[room]:
                log.info(_("Leaving MUC room {!r}.").format(room))
                plugin.leaveMUC(room, nick)
        for room, nick in self.muc_nicks.items():
            if room not in plugin.rooms:
                log.info(_("Joining MUC room {!r} as {!r}.").format(room, nick))
                plugin.joinMUC(room, nick)

    def get_user_config(self, jid):
        """
        Get UserConfig corresponding to the given JID.

        Arguments:
            jid         --- JID object or JID string.

        """
        if isinstance(jid, str):
            jid = JID(jid)
        user = JID("")

        plugin = self.plugin.get("xep_0045")
        if plugin is not None and jid.bare in plugin.rooms:
            real_jid = plugin.getJidProperty(jid.bare, jid.resource, "jid")
            if real_jid is not None and real_jid.full not in ("", jid.full):
                user = self._match_jid(real_jid)

        if user.full == "":
            user = self._match_jid(jid)

        conf = self.users.get(user)
        if conf is None:
            conf = UserConfig(0, "en")
        log.debug(_("Using {!r} for JID {!r}.").format(conf, jid.full))
        return conf

    def _match_jid(self, jid):
        """ Find user mask corresponding to the given JID. """
        for mask in self.users:
            if mask is not None and mask.domain == jid.domain and mask.user in ("", jid.user) and mask.resource in ("", jid.resource):
                return mask
        return JID("")

    def register_bot_plugin(self, name, config, module=None):
        """
        Register and configure a bot plugin.

        Arguments:
            name        --- The name of the plugin class. Plugin names must be unique.
            config      --- Plugin configuration.
            module      --- Name of the custom module containing the plugin class.

        """
        log.info(_("Registering bot plugin {!r}.").format(name))
        try:
            # Prevent re-registration
            if name in self.bot_plugins:
                log.warn(_("Bot plugin {!r} is already registered.").format(name))
                raise ValueError

            # Import the given module that contains the plugin.
            if module is None:
                module = "plugins.{}".format(name)
            elif not isinstance(module, str):
                raise TypeError
            if module in sys.modules:
                reload(sys.modules[module])
                module = sys.modules[module]
            else:
                module = __import__(module, fromlist=[name])
            plugin = getattr(module, name)

            # Inject SleekXMPP plugins
            if hasattr(plugin, "sleek_plugins"):
                for dep in plugin.sleek_plugins:
                    if dep in self.plugin:
                        setattr(plugin, dep, self.plugin[dep])
                    else:
                        log.warn(_("Bot plugin {!r} needs SleekXMPP plugin {!r}.".format(name, dep)))
                        raise RuntimeError

            # Initialize the plugin
            self.bot_plugins[name] = plugin(self, config)

        except:
            log.exception(_("Loading of bot plugin {!r} FAILED.").format(name))

    def deregister_bot_plugins(self):
        """
        Deregister all registered bot plugins.

        """
        for plugin in list(self.bot_plugins.keys()):
            self.deregister_bot_plugin(plugin)

    def deregister_bot_plugin(self, name):
        """
        Deregister a bot plugin.

        Arguments:
            name        --- The name of the plugin class. Plugin names must be unique.

        """
        log.info(_("Deregistering bot plugin {!r}.").format(name))
        if name in self.bot_plugins:
            if hasattr(self.bot_plugins[name], "shutdown"):
                log.debug(_("Calling the shutdown method of bot plugin {!r}.").format(name))
                self.bot_plugins[name].shutdown(self)
            del self.bot_plugins[name]

    def add_help_topic(self, topic, title=None, body=None):
        """
        Add help topic.

        Argumenst:
            topic       --- The topic name.

        Keyworded arguments:
            title       --- Short title of the topic.
            body        --- Main text of the topic.

        """
        self.help_topics[topic] = Help(title, body)

    def add_command(self, name, callback, htitle=None, hbody=None, husage=None, level=None):
        """
        Add command and corresponding help topic.

        Arguments:
            name        --- Name of the command.
            callback    --- Command callback.

        Keyworded arguments:
            htitle      --- Short title for the help topic.
            hbody       --- Main text of the help topic.
            husage      --- Example of the command usage.
            level       --- Required level for the command (None for default setting).

        """
        if hbody is None:
            hbody = []
        elif isinstance(hbody, str):
            hbody = [hbody]
        else:
            hbody = list(hbody)
        if len(hbody) > 0:
            hbody.append("\n")
        hbody.append(__("Usage"))
        if husage is None:
            hbody.append(": {}{}".format(self.cmd_prefix, name))
        else:
            hbody.append(": {}{} ".format(self.cmd_prefix, name))
            if isinstance(husage, str):
                husage = [husage]
            for part in husage:
                hbody.append(part)
        self.add_help_topic(name, htitle, hbody)
        if level is None and "command:"+name not in self.permissions:
            self.permissions["command:"+name] = self.permissions.get("command", 0)
        self.commands[name] = callback

    def get_translations(self, lang):
        """
        Get gettext translations instance for a specified language.
        Creates one, if needed.

        Arguments:
            lang        --- Translation language.

        """
        localedir = os.path.join(os.path.dirname(__file__), "locale")
        if lang not in self.translations:
            self.translations[lang] = gt.translation("keelsbot", localedir=localedir, codeset="utf-8", languages=[lang], fallback=True)
        return self.translations[lang]

    def gettext(self, message, lang):
        """
        Call gettext method on the translations instance of a specified language.

        Arguments:
            message     --- Message to translate.
            lang        --- Translation language.

        """
        return self.get_translations(lang).gettext(message)

    def ngettext(self, singular, plural, n, lang):
        """
        Call ngettext method on the translations instance of a specified language.

        Arguments:
            singular    --- Singular form of the message to translate.
            plural      --- Plural form of the message to translate.
            n           --- Number to use for determination of plural form.
            lang        --- Translation language.

        """
        return self.get_translations(lang).ngettext(singular, plural, n)



class KeelsBot(BaseBot):
    """
    KeelsBot main class.

    Attributes:
        auto_restart    --- Flag to determine if the bot should be automatically restarted.
        config_file     --- Path to the configuration file.

    Methods:
        reload                  --- Reloads the config file and makes appropriate runtime changes.
        restart                 --- Completely restart the bot.
        load_config             --- Load config file.
        config_sleek_plugins    --- Load configuration and register SleekXMPP plugins.
        config_bot_plugins      --- Load configuration and register bot plugins.

    """

    auto_restart = False

    def __init__(self, config_file):
        """
        Arguments:
            config_file --- Path to the configuration file.

        """
        self.config_file = config_file
        bot_config = self.load_config()

        auth = bot_config.find("/auth").attrib
        BaseBot.__init__(self, auth)

        self.config_sleek_plugins(bot_config)
        self.config_bot_plugins(bot_config)

    def reload(self):
        """
        Reloads the config file and makes appropriate runtime changes.
        Causes all plugins to be reloaded (or unloaded). The XMPP stream, and channels will not be disconnected.

        """
        log.warn(_("Cleaning bot configuration before reload."))
        self.deregister_bot_plugins()
        self.permissions = {}
        self.commands = {}
        self.help_topics = {}
        self.translations = {}

        log.info(_("Reloading bot configuration."))
        bot_config = self.load_config()
        self.config_bot_plugins(bot_config)
        self.sync_rooms()

    def restart(self):
        """
        Completely restart the bot.

        """
        self.auto_restart = True
        log.warn(_("Restarting the bot."))
        self.die()

    def load_config(self):
        """
        Load config file.

        """
        config = ET.parse(self.config_file)

        # Configure persistent storage.
        storage = config.find("/storage")
        if storage is not None:
            self.store = Storage(storage.get("file"))
        else:
            self.store = None
            log.warn(_("No storage element found in config file - proceeding with no persistent storage, plugin behaviour may be undefined."))

        # Configure permissions
        self.permissions = {}
        default_level = 0
        default_permission = config.find("/permissions")
        if default_permission is not None:
            default_level = int(default_permission.get("level", default_level))
            for command in default_permission.findall("command"):
                level = int(command.get("level", default_level))
                self.permissions["command:"+command.text] = level
        self.permissions["command"] = default_level

        # Configure users
        self.users = {}
        default_level = 0
        default_lang = "en"
        default_user = config.find("/users")
        if default_user is not None:
            default_level = int(default_user.get("level", default_level))
            default_lang = default_user.get("lang", default_lang)
            for user in default_user.findall("jid"):
                level = int(user.get("level", default_level))
                lang = user.get("lang", default_lang)
                self.users[JID(user.text)] = UserConfig(level, lang)
        self.users[None] = UserConfig(default_level, default_lang) # Default user config

        # Configure MUCs
        self.muc_nicks = {}
        for plugin in config.findall("/sleek/plugin"):
            if plugin.get("name") == "xep_0045":
                for muc in plugin.findall("muc"):
                    room = muc.get("room")
                    if room is None:
                        log.error(_("Ignoring MUC with empty room attribute."))
                        continue
                    self.muc_nicks[room] = muc.get("nick", "KeelsBot")
                break

        return config

    def config_sleek_plugins(self, config):
        """
        Load configuration and register SleekXMPP plugins.

        Arguments:
            config          --- Bot configuration.

        """
        self.plugin_whitelist = []
        self.plugin_config = {}
        for plugin in config.findall("/sleek/plugin"):
            name = plugin.get("name")
            if "name" is None:
                log.error(_("Ignoring unnamed SleekXMPP plugin."))
                continue
            self.plugin_whitelist.append(name)
            conf = plugin.find("config")
            if conf is not None:
                self.plugin_config[name] = dict(conf.attrib)

        # Indentification of the bot
        if "xep_0092" in self.plugin_whitelist:
            self.plugin_config["xep_0092"] = self.plugin_config.get("xep_0092", {})
            self.plugin_config["xep_0092"]["name"] = self.plugin_config["xep_0092"].get("name", "KeelsBot")
            self.plugin_config["xep_0092"]["version"] = self.plugin_config["xep_0092"].get("version", __version__)

        self.register_plugins()

    def config_bot_plugins(self, config):
        """
        Load configuration and register bot plugins.

        Arguments:
            config          --- Bot configuration.

        """
        for plugin in config.findall("/keels/plugin"):
            name = plugin.get("name")
            if "name" is None:
                log.error(_("Ignoring unnamed bot plugin."))
                continue
            log.debug(_("Adding bot plugin {!r}.").format(name))
            config = self._parse_plugin_config(list(plugin))
            self.register_bot_plugin(name, config, plugin.get("module"))

    def _parse_plugin_config(self, elements):
        """ Parse plugin configuration """
        config = {}
        for child in elements:
            current = dict(child.attrib)
            if child.tag == "config":
                config["config"] = current
            else:
                if child.tag not in config:
                    config[child.tag] = []
                config[child.tag].append(current)
            current.update(self._parse_plugin_config(list(child)))
        return config



if __name__ == "__main__":
    # Setup console output logging
    colored_handler = colterm.ColoredStreamHandler(fmt="%(asctime)s %(levelname)-8s %(name)s >> %(message)s", datefmt="%Y-%m-%d %X")
    rootlog = logging.getLogger("")
    rootlog.addHandler(colored_handler)
    rootlog.setLevel(logging.WARN)

    # Parse command line arguements
    optp = OptionParser(formatter=IndentedHelpFormatter(max_help_position=40), conflict_handler="resolve", version="%prog "+__version__)
    optp.add_option("-n", "--no-color", help=_("disable usage of colored output"), dest="color", action="store_false", default=True)
    optp.add_option("-q", "--quiet", help=_("set logging to ERROR"), dest="loglevel", action="store_const", const=logging.ERROR, default=logging.WARN)
    optp.add_option("-v", "--verbose", help=_("set logging to INFO"), dest="loglevel", action="store_const", const=logging.INFO)
    optp.add_option("-d", "--debug", help=_("set logging to DEBUG"), dest="loglevel", action="store_const", const=logging.DEBUG)
    optp.add_option("-D", "--Debug", help=_("set logging to ALL"), dest="loglevel", action="store_const", const=0)
    optp.add_option("-c", "--config", help=_("path to config file"), dest="configfile", default="config.xml")

    opts,args = optp.parse_args()
    rootlog.setLevel(opts.loglevel)
    colterm.use_color(opts.color)

    # Check requirements
    minVersion = "3.1"
    if python_version() < minVersion:
        log.critical(_("You need at least Python {} to run this script.")).format(minVersion)

    config_file = os.path.expanduser(opts.configfile)
    if not os.path.isfile(config_file):
        log.critical(_("Config file {!r} not found.").format(config_file))

    try:
        auto_restart = True
        while auto_restart:
            bot = KeelsBot(config_file)
            bot.run()
            auto_restart = bot.auto_restart
    except Exception:
        log.exception(_("Unexpected error... killing the bot."))
        bot.die()
        sleep(2)
        raise SystemExit
