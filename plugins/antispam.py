# -*- coding: utf-8 -*-
"""
antispam plugin: MUC spam protection.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import logging
import time

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class antispam:
    sleek_plugins = ("xep_0045",)
    limit_types = {}
    rooms = {}

    def __init__(self, bot, config):
        self.get_user_config = bot.get_user_config
        self.gettext = bot.gettext
        self.ngettext = bot.ngettext

        self.limit_types["message"] = self.limit_message
        self.limit_types["character"] = self.limit_character

        for muc in config.get("muc", []):
            for limit in muc.get("limit", []):
                if limit.get("type") not in self.limit_types:
                    log.error(_("Configuration error - type attribute of limit required and must be one of {}.").format(", ".join(self.limit_types.keys())))
                    muc["limit"].remove(limit)
                    continue
                try:
                    for attr in ("interval", "limit", "expiration"):
                        limit[attr] = int(limit[attr])
                except:
                    log.error(_("Configuration error - {} attribute of limit required and must be digit.").format(attr))
                    muc["limit"].remove(limit)
                    continue

            if len(muc.get("limit", [])) == 0:
                log.error(_("Configuration error - no limits given."))
                continue

            if "room" not in muc:
                log.error(_("Configuration error - room attribute of muc required."))
                continue

            conf = self.rooms[muc["room"]] = {}
            conf["noban"] = "noban" in muc
            conf["limits"] = list(muc["limit"])
            conf["spammers"] = {}
            conf["history"] = {}
            log.info(_("Enabling spam protection in room {}.").format(muc["room"]))
            bot.add_event_handler("muc::{}::message".format(muc["room"]), self.check_spam, threaded=False)

    def shutdown(self, bot):
        for room in self.rooms:
            bot.del_event_handler("muc::{}::message".format(room), self.check_spam)

    def limit_message(self, item):
        return 1

    def limit_character(self, item):
        return len(item[1])

    def check_spam(self, msg):
        """ Keep track of users activity. """
        room = msg["mucroom"]
        nick = msg["mucnick"]

        bot_nick = self.xep_0045.ourNicks.get(room, "")
        if nick in ("", bot_nick) or room not in self.xep_0045.getJoinedRooms() or "body" not in msg.keys():
            # system msg, own msg, or invalid
            return

        bot_role = self.xep_0045.getJidProperty(room, bot_nick, "role")
        if bot_role != "moderator":
            # We don't have rights
            return

        nick_role = self.xep_0045.getJidProperty(room, nick, "role")
        bot_affiliation = self.xep_0045.getJidProperty(room, bot_nick, "affiliation")
        nick_affiliation = self.xep_0045.getJidProperty(room, nick, "affiliation")
        if nick_affiliation == "owner" or (nick_affiliation == "admin" and bot_affiliation != "owner") or (nick_role == "moderator" and bot_affiliation not in ("admin", "owner")):
            # Power user
            return

        jid = str(self.xep_0045.getJidProperty(room, nick, "jid"))
        now = int(time.time())
        noban = self.rooms[room]["noban"]
        limits = self.rooms[room]["limits"]
        spammers = self.rooms[room]["spammers"]
        history = self.rooms[room]["history"]
        if jid not in history:
            history[jid] = []
        history[jid].append((now, msg.get("body", "")))

        max_interval = 0
        max_expiration = 0
        action = None
        for limit in limits:
            max_interval = max(limit["interval"], max_interval)
            max_expiration = max(limit["expiration"], max_expiration)
            if action is not None:
                # We have already taken some action -> ignore the remaining limits
                continue
            age = now - limit["interval"]
            count = 0
            callback = self.limit_types[limit["type"]]
            for item in history[jid]:
                if item[0] >= age:
                    count += callback(item)
            if count >= limit["limit"]:
                age = now - limit["expiration"]
                if jid not in spammers or spammers[jid][0] < age:
                    action = "warn"
                    log.info(_("Warning {!r} in room {}.").format(nick, room))
                    uc = self.get_user_config(msg["from"])
                    msg.reply(nick + ": " + self.gettext("Stop spamming!", uc.lang)).send()
                elif spammers[jid][1] == "warn" or noban or bot_affiliation not in ("admin", "owner"):
                    action = "kick"
                    log.info(_("Kicking {!r} from room {}.").format(jid, room))
                    self.xep_0045.setRole(room, jid=jid, role="none", reason="spam")
                else:
                    action = "ban"
                    log.warn(_("Banning {!r} from room {}.").format(jid, room))
                    return self.xep_0045.setAffiliation(room, jid=jid, affiliation="outcast", reason="spam")
                spammers[jid] = (now, action)

        # Cleanup
        age = now - max_interval
        for jid in list(history.keys()):
            if history[jid][-1][0] < age:
                del history[jid]
            else:
                while len(history[jid]) > 0 and history[jid][0][0] < age:
                    del history[jid][0]
        age = now - max_expiration
        for jid in list(spammers.keys()):
            if spammers[jid][0] < age:
                del spammers[jid]

        log.debug(_("Got {} users in history and {} in spammers.").format(len(history), len(spammers)))
