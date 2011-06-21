# -*- coding: utf-8 -*-
"""
pastebin plugin: Sends code snippetes to pastebin.com.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class pastebin:
    lang = "text"
    expiration = "1D"

    def __init__(self, bot, config):
        self.get_our_nick = bot.get_our_nick
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext

        config = config.get("config", {})
        self.lang = config.get("lang", self.lang)
        self.expiration = config.get("expiration", self.expiration)

        bot.add_command("paste", self.paste, "Pastebin", (__("Sends code snippet to pastebin.com\nAt first line are optional arguments separated by space in an arbitrary order - expiration (10M = 10 minutes, 1H = 1 hour, 1D = 1 day, 1M = 1 month, N = never), langauge format (see http://pastebin.com/api) and whether to send the link directly to MUC (1, defaults to 0 = send the link back to user). Default expiration is "), self.expiration, __(" and language "), self.lang + ".\n", __("All other lines are treated as code content.")), ("[10M|1H|1D|1M|N] [lang] [0|1]\n", __("code")))

    def paste(self, command, args, msg, uc):
        paste = args.split("\n", 1)
        if len(paste) < 2:
            return self.gettext("Invalid input, see help.", uc.lang)

        to_muc = False
        lang = self.lang
        expiration = self.expiration

        code = paste[1]

        arguments = paste[0].split(" ")
        for param in arguments:
            if param.upper() in ("10M", "1H", "1D", "1M", "N"):
                expiration = param.upper()
            elif param in ("0", "1"):
                to_muc = param == "1"
            elif param != "":
                lang = param.lower()

        if msg["type"] == "groupchat":
            author = msg["mucnick"]
        elif self.get_our_nick(msg["from"].bare) is not None:
            author = msg["from"].resource
        elif "nick" in msg.keys():
            author = msg["nick"]
        else:
            author = msg["from"].user

        data = {"paste_code":code, "paste_name":author, "paste_expire_date":expiration, "paste_format":lang}
        log.debug(data)

        try:
            data = urllib.parse.urlencode(data).encode("utf-8")
            response = urllib.request.urlopen("http://pastebin.com/api_public.php", data, 10).read().decode("utf-8")
            url = str(response.split("\n", 1)[0])
            if not url.startswith("http://pastebin.com/"):
                raise ValueError(_("Unexpected response:") + "\n{}".format(response))
        except:
            log.exception(_("Unexpected error while getting pastebin URL."))
            return self.gettext("ERROR", uc.lang)

        if to_muc and msg["type"] != "groupchat" and self.get_our_nick(msg["from"].bare) is not None:
            msg["type"] = "groupchat"
            return self.gettext("{} sent code snippet {}", uc.lang).format(author, url)
        else:
            return url
