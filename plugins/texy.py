# -*- coding: utf-8 -*-
"""
texy plugin: Parse Texy! syntax.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging
import os.path
from subprocess import getoutput

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class texy:
    def __init__(self, bot, config):
        self.texy = "php {}".format(os.path.join(os.path.dirname(__file__), "..", "misc", "texy.process.php"))
        bot.add_command("texy", self.process, "Texy!", __("Return the message processed by Texy! If not message is given, return Texy! version."), __("[message]"))

    def process(self, command, args, msg, uc):
        if args == "":
            return "Texy! {}".format(getoutput(self.texy))
        return getoutput("{} '{}'".format(self.texy, args.replace("'", "\\'")))
