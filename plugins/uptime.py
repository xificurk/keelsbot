# This Python file uses the following encoding: utf-8
"""
    uptime.py - A plugin for displaying bot's uptime.
    Copyright (C) 2009 Petr Morávek
    The code is based on similar plugin for SleekBot.

    KeelsBot is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    KeelsBot is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this software; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import logging
import datetime, time

class uptime(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = u"'Uptime' umožňuje uživatelům ptát se na uptime bota.\nAutor: Petr Morávek"
        self.bot.addCommand('uptime', self.handle_uptime, 'Uptime bota', u"Jak dlouho už bot běží?", 'uptime')
        self.started = datetime.timedelta(seconds = time.time())

    def getStringUpt(self, time):
        days = time.days
        seconds = time.seconds
        
        months = hours = minutes = 0
        response = ""

        months = days / 30
        days -= months * 30
        if months > 0:
            months_str = u"%d měsíc" % months
            if months > 4:
                months_str += u"ů"
            elif months > 1:
                months_str += u"e"
            response += months_str

        if len(response) > 0 or days > 0:
            if days > 4 or days == 0:
                days_str = u"%d dnů" % days
            elif days > 1:
                days_str = u"%d dny" % days
            else:
                days_str = u"%d den" % days
            if len(response) > 0:
                return response + " a " + days_str
            response += days_str

        hours = seconds / 3600
        seconds -= hours * 3600
        if len(response) > 0 or hours > 0:
            hours_str = "%d hodin" % hours
            if hours > 1 and hours <= 4:
                hours_str += "y"
            elif hours == 1:
                hours_str += "u"
            if len(response) > 0:
                return response + " a " + hours_str
            response += hours_str

        minutes = seconds / 60
        seconds -= minutes * 60
        if len(response) > 0 or minutes > 0:
            minutes_str = "%d minut" % minutes
            if minutes > 1 and minutes <= 4:
                minutes_str += "y"
            elif minutes == 1:
                minutes_str += "u"
            if len(response) > 0:
                return response + " a " + minutes_str
            response += minutes_str

        if len(response) > 0 or seconds > 0:
            seconds_str = "%d sekund" % seconds
            if seconds > 1 and seconds <= 4:
                seconds_str += "y"
            elif seconds == 1:
                seconds_str += "u"
            if len(response) > 0:
                return response + " a " + seconds_str
            return seconds_str

    def handle_uptime(self, command, args, msg):
        now = datetime.timedelta(seconds = time.time())
        diff = now - self.started
        return u"Jsem vzhůru už %s" % self.getStringUpt(diff) + "."