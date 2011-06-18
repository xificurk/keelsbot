# -*- coding: utf-8 -*-
"""
uptime plugin: Displays the bot's uptime.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging
import time

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class uptime:
    def __init__(self, bot, config):
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext
        self.started = time.time()

        bot.add_command("uptime", self.uptime, __("Bot's uptime"), __("Time since the last bot reload."))

    def uptime(self, command, args, msg, uc):
        delta = self.format_timedelta(time.time() - self.started, uc.lang)
        log.debug(delta)
        log.debug("I'm up {}.".format(delta))
        return self.gettext("I'm up {}.", uc.lang).format(delta)

    def format_timedelta(self, delta, lang):
        parts = []

        months = int(delta/3600/24/30)
        if months > 0:
            delta -= months*3600*24*30
            parts.append(self.ngettext("{} month", "{} months", months, lang).format(months))

        days = int(delta/3600/24)
        if days > 0 or len(parts) > 0:
            delta -= days*3600*24
            parts.append(self.ngettext("{} day", "{} days", days, lang).format(days))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        hours = int(delta/3600)
        if hours > 0 or len(parts) > 0:
            delta -= hours*3600
            parts.append(self.ngettext("{} hour", "{} hours", hours, lang).format(hours))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        minutes = int(delta/60)
        if minutes > 0 or len(parts) > 0:
            delta -= minutes*60
            parts.append(self.ngettext("{} minute", "{} minutes", minutes, lang).format(minutes))
        if len(parts) > 1:
            return self.gettext(" and ", lang).join(parts)

        seconds = int(delta)
        parts.append(self.ngettext("{} second", "{} seconds", seconds, lang).format(seconds))
        return self.gettext(" and ", lang).join(parts)
