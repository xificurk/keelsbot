# -*- coding: utf-8 -*-
"""
    basebot.py - basic bot class.
    Copyright (C) 2007 Nathan Fritz 
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

import logging

LOG_COMM = 8
logging.addLevelName(LOG_COMM, "COMM")


class basebot(object):
    def __init__(self):
        self.log = logging.getLogger("basebot")
        self.cmd_prefix = "!"
        self.minAccessLevel = 0
        self.clearCommands()
        self.add_event_handler("message", self.handleMessageEvent, threaded=True)


    def clearCommands(self):
        self.commands = {}
        self.help = {}


    def getAccessLevel(self, event):
        """ Returns access level of the sender of the event (negative value means bot should ignore this).
            Override this to get better access control.
        """
        if event["type"] == "groupchat":
            if event["from"].full == event["mucroom"] or event["mucroom"] not in self.rooms or self.rooms[event["mucroom"]] == event["mucnick"]:
                #system, error, or own message
                return -666
        return 0


    def handleMessageEvent(self, msg):
        """ Parse message event and run the command
        """
        self.log.log(LOG_COMM, msg)
        level = self.getAccessLevel(msg)
        self.log.debug("User lvl: {0}, MinAclLevel: {1}".format(level, self.minAccessLevel))
        if level < self.minAccessLevel or level < 0:
            return
        message = msg.get("body", "")
        if message.startswith(self.cmd_prefix):
            # Remove cmd_prefix from message
            message = message[len(cmd_prefix):]

            # Get command name
            command = message.split("\n", 1)[0].split(" ", 1)[0]
            if len(command) == 0:
                # No command name -> return
                return

            # Parse arguments
            args = message[len(command)+1:]

            self.log.debug("Command '{0}' with args '{1}'".format(command, args))

            if command in self.commands and self.commands[command]["level"] <= level:
                response = self.commands[command]["pointer"](command, args, msg)
                if msg["type"] == "groupchat":
                    self.sendMessage(msg["mucroom"], "{0}: {1}".format(msg["mucnick"], response), mtype="groupchat")
                else:
                    self.sendMessage(msg["from"].full, response, mtype=msg.get("type", "chat"))


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


    def getCommandAccessLevel(self, command):
        """ Determine required access level for the command.
            Override this to get better access control.
        """
        return 0


    def addIMCommand(self, command, pointer):
        """ Compatibility with SleekBot plugins.
        """
        self.addCommand(command, pointer)


    def addMUCCommand(self, command, pointer):
        """ Compatibility with SleekBot plugins.
        """
        self.addCommand(command, pointer)
