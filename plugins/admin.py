# -*- coding: utf-8 -*-
"""
admin plugin: Basic administration of the bot.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2007 Kevin Smith",
                 "Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class admin:
    loglevels = {"ALL":0, "DEBUG":10, "INFO":20, "WARNING":30, "ERROR":40, "CRITICAL":50}

    def __init__(self, bot, config):
        self.bot_reload = bot.reload
        self.bot_restart = bot.restart
        self.bot_die = bot.die
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext

        bot.add_command("reload", self.reload, __("Reload"), __("Reload the bot configuration and apply changes without disconnecting."))
        bot.add_command("restart", self.restart, __("Restart"), __("Completely restart the bot."))
        bot.add_command("die", self.die, __("Die"), __("Kill the bot."))
        bot.add_command("loglevel", self.loglevel, __("Log level"), __("Set the level of logging."), "<0-50|{}>".format("|".join(sorted(self.loglevels.keys()))))
        bot.add_command("level", self.level, __("User level"), __("Display user's access level."))

    def reload(self, command, args, msg, uc):
        self.bot_reload()
        return self.gettext("Reloaded, boss.", uc.lang)

    def restart(self, command, args, msg, uc):
        self.bot_restart()

    def die(self, command, args, msg, uc):
        self.bot_die()

    def loglevel(self, command, args, msg, uc):
        if args.isdigit():
            args = int(args)
        else:
            args = args.upper()
            if args in self.loglevels:
                args = self.loglevels[args]
            else:
                return self.gettext("You must input the number in range 0-50, or one of the values {}.", uc.lang).format(", ".join(sorted(self.loglevels.keys())))

        if args < 0 or args > 50:
            return self.gettext("You must input the number in range 0-50, or one of the values {}.", uc.lang).format(", ".join(sorted(self.loglevels.keys())))

        logging.getLogger("").setLevel(args)
        return self.gettext("Log level changed...", uc.lang)

    def level(self, command, args, msg, uc):
        return self.gettext("You're on level {}.", uc.lang).format(uc.level)
