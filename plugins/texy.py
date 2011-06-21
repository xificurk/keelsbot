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
import subprocess

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class texy:
    php_binary = "php"
    texy_path = os.path.join(os.path.dirname(__file__), "..", "misc", "texy.process.php")

    def __init__(self, bot, config):
        bot.add_command("texy", self.texy, "Texy!", __("Return the message processed by Texy! If not message is given, return Texy! version."), __("[message]"))

    def texy(self, command, args, msg, uc):
        cmd_args = [self.php_binary, self.texy_path]
        if args != "":
            cmd_args.append(args)
        result = subprocess.Popen(cmd_args, stdout=subprocess.PIPE).communicate()
        if result[1] not in (0, None):
            log.error(_("Could not process:\n{}".format(args)))
            return
        return result[0].decode("utf-8")
