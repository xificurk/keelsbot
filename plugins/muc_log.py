# -*- coding: utf-8 -*-
"""
muc_log plugin: Logs traffic in MUC.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2008 Kevin Smith",
                 "Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


import datetime
import logging
import re
import threading
from xml.etree import cElementTree as ET

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class muc_log:
    loggers = {}

    def __init__(self, bot, config):
        for muc_log in config.get("log", []):
            room = muc_log.get("room")
            if room is None:
                log.error(_("Configuration error - room attribute of log required."))
                continue

            if "file" in muc_log:
                log.info(_("Starting logging of room {!r} to file {}.").format(room, muc_log["file"]))
                logger = self.loggers[room] = FileLogger(muc_log["file"])
            else:
                log.error(_("Configuration error - file attribute of log required."))
                continue

            bot.add_event_handler("muc::{}::message".format(room), logger.process_message, threaded=False)
            bot.add_event_handler("muc::{}::subject".format(room), logger.process_subject, threaded=False)
            bot.add_event_handler("muc::{}::got_online".format(room), logger.process_got_online, threaded=False)
            bot.add_event_handler("muc::{}::got_offline".format(room), logger.process_got_offline, threaded=False)

    def shutdown(self, bot):
        for room, logger in self.loggers.items():
            bot.del_event_handler("muc::{}::message".format(room), logger.process_message)
            bot.del_event_handler("muc::{}::subject".format(room), logger.process_subject)
            bot.del_event_handler("muc::{}::got_online".format(room), logger.process_got_online)
            bot.del_event_handler("muc::{}::got_offline".format(room), logger.process_got_offline)
            logger.quit()


class DummyLogger:
    status_codes = (301, 307)

    def quit(self):
        pass

    def process_message(self, msg):
        subject = msg.get("subject", "")
        if msg.get("subject", "") != "":
            return
        self.log_message(msg["mucnick"], msg.get("body", ""))

    def process_subject(self, msg):
        subject = msg.get("subject", "")
        if subject == "":
            return
        nick = msg["mucnick"]
        body = msg.get("body", "")
        if nick == "" and body != "":
            match = re.match("^(.*?) has set the subject to:", body)
            if match is not None:
                nick = match.group(1)
        self.log_subject(nick, subject)

    def process_got_online(self, pr):
        self.log_got_online(pr["muc"]["nick"], pr["muc"]["jid"].full, pr["muc"]["role"])

    def process_got_offline(self, pr):
        status = pr.get("status", "")
        code = None
        xstatus = pr["muc"].xml.find("{{{}}}status".format(pr["muc"].namespace))
        if xstatus is not None:
            xcode = int(xstatus.get("code"))
            if xcode in self.status_codes:
                code = xcode
                xreason = pr["muc"].getXMLItem().find("{{{}}}reason".format(pr["muc"].namespace))
                if xreason is not None:
                    status = xreason.text
        self.log_got_offline(pr["muc"]["nick"], pr["muc"]["jid"].full, status, code)

    def log_message(self, nick, body):
        pass

    def log_subject(self, nick, subject):
        pass

    def log_got_online(self, nick, jid, role):
        pass

    def log_got_offline(self, nick, jid, status, code):
        pass


class FileLogger(DummyLogger):
    datetime_format = "%Y-%m-%d %X"
    status_codes = {307: _("has been kicked"), 301: _("has been banned")}

    def __init__(self, filename):
        self.lock = threading.Lock()
        log.debug(_("Openning log file {!r}.").format(filename))
        self.logfile = open(filename, "a")
        self.log("--- " + _("Logging started"))

    def quit(self):
        with self.lock:
            self.logfile.close()

    def log(self, line):
        with self.lock:
            try:
                self.logfile.write("{:{}} {}\n".format(datetime.datetime.now(), self.datetime_format, line.replace("\n", "\n\t")))
                self.logfile.flush()
            except ValueError:
                pass

    def log_message(self, nick, body):
        if nick == "":
            # System message
            line = "-!- {}".format(body)
        elif body.startswith("/me "):
            # Action message
            line = " * {} {}".format(nick, body[4:])
        else:
            # Normal message
            line = "<{}> {}".format(nick, body)
        self.log(line)

    def log_subject(self, nick, subject):
        if nick == "":
            line = "-!- {}: {}".format(_("Subject has been set to"), subject)
        else:
            line = "-!- {} {}: {}".format(nick, _("has set the subject to"), subject)
        self.log(line)

    def log_got_online(self, nick, jid, role):
        if jid != "":
            nick += " ({})".format(jid)
        line = "-!- {} {} {}".format(nick, _("has joined the room as"), _(role))
        self.log(line)

    def log_got_offline(self, nick, jid, status, code):
        if jid != "":
            nick += " ({})".format(jid)
        line = "-!- {} {}".format(nick, self.status_codes.get(code, _("has left the room")))
        if status != "":
            line += " [{}]".format(status)
        self.log(line)
