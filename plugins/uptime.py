# -*- coding: utf-8 -*-
"""
    plugins/uptime.py - A plugin for displaying bot's uptime.
    Copyright (C) 2009-2010 Petr Morávek
    This code was inspired by similar plugin for SleekBot.

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


class uptime(object):
    def __init__(self, bot, config):
        self.about = "'Uptime' umožňuje vypisuje uptime bota.\nAutor: Petr Morávek"
        bot.addCommand("uptime", self.uptime, "Uptime bota", "Jak dlouho už bot běží?", "uptime")
        self.started = datetime.datetime.now()


    def uptime(self, command, args, msg):
        diff = datetime.datetime.now() - self.started
        return "Jsem vzhůru už {0}.".format(self.formatTimeDiff(diff))


    def formatTimeDiff(self, time):
        days = time.days
        seconds = time.seconds

        months = hours = minutes = 0
        response = ""

        months = int(days / 30)
        days -= months * 30
        if months > 0:
            monthsStr = "{0} měsíc".format(months)
            if months > 4:
                monthsStr += "ů"
            elif months > 1:
                monthsStr += "e"
            response = monthsStr

        if len(response) > 0 or days > 0:
            if days > 4 or days == 0:
                daysStr = "{0} dnů".format(days)
            elif days > 1:
                daysStr = "{0} dny".format(days)
            else:
                daysStr = "{0} den".format(days)
            if len(response) > 0:
                return response + " a " + daysStr
            response = daysStr

        hours = int(seconds / 3600)
        seconds -= hours * 3600
        if len(response) > 0 or hours > 0:
            hoursStr = "{0} hodin".format(hours)
            if hours > 1 and hours <= 4:
                hoursStr += "y"
            elif hours == 1:
                hoursStr += "u"
            if len(response) > 0:
                return response + " a " + hoursStr
            response = hoursStr

        minutes = int(seconds / 60)
        seconds -= minutes * 60
        if len(response) > 0 or minutes > 0:
            minutesStr = "{0} minut".format(minutes)
            if minutes > 1 and minutes <= 4:
                minutesStr += "y"
            elif minutes == 1:
                minutesStr += "u"
            if len(response) > 0:
                return response + " a " + minutesStr
            response = minutesStr

        if len(response) > 0 or seconds > 0:
            secondsStr = "{0} sekund".format(seconds)
            if seconds > 1 and seconds <= 4:
                secondsStr += "y"
            elif seconds == 1:
                secondsStr += "u"
            if len(response) > 0:
                return response + " a " + secondsStr
            return secondsStr
