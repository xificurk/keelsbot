# -*- coding: utf-8 -*-
"""
help plugin: Displays help for commands and other topics.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class help:
    def __init__(self, bot, config):
        self.cmd_prefix = bot.cmd_prefix
        self.commands = bot.commands
        self.get_command_level = bot.get_command_level
        self.help_topics = bot.help_topics
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext

        bot.add_command("help", self.help, __("Help"), __("If no topic was given, display the list of available commands and other help topics. Otherwise display the help for a given topic."), __("[command/topic]"))
        bot.add_command("commands", self.commands, __("Commands"), __("Display list of available commands."))

    def commands(self, command, args, msg, uc):
        response = self.gettext("Available commands", uc.lang) + ":\n"
        for cmd in sorted(self.commands.keys()):
            if self.get_command_level(cmd) > uc.level:
                continue
            response += self.cmd_prefix + cmd
            if self.help_topics[cmd].title is not None:
                response += " -- " + self.gettext(self.help_topics[cmd].title, uc.lang)
            response += "\n"
        response = response.strip("\n")
        return response

    def help(self, command, args, msg, uc):
        response = ""
        if len(args) == 0:
            response += self.commands(command, args, msg, uc) + "\n"
            start = True
            for topic in sorted(self.help_topics.keys()):
                if topic in self.commands:
                    continue
                if start:
                    response += "\n" + self.gettext("Other available help topics", uc.lang) + ":\n"
                    start = False
                response += topic
                if self.help_topics[topic].title is not None:
                    response += " -- " + self.gettext(self.help_topics[topic].title, uc.lang)
                response += "\n"
            args = "help"
            response += "---------\n"

        if args.startswith(self.cmd_prefix) and len(args) > len(self.cmd_prefix):
            args = args[len(self.cmd_prefix):]

        if args not in self.help_topics or (args in self.commands and uc.level < self.get_command_level(args)):
            return self.gettext("Don't know...", uc.lang)

        help_topic = self.help_topics[args]
        if help_topic.title is not None:
            response += self.gettext(help_topic.title, uc.lang) + "\n"
        if help_topic.body is not None:
            body = help_topic.body
            if isinstance(body, str):
                body = [body]
            for part in body:
                response += self.gettext(part, uc.lang)
        response = response.strip("\n")

        return response
