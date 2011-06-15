# -*- coding: utf-8 -*-
"""
feedreader plugin: Displays help and other topics.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"

__version__ = "0.5.0"


from html.parser import HTMLParser
import logging
import queue
import threading
import time
import urllib.request
from xml.etree import cElementTree as ET

log = logging.getLogger(__name__)
__ = lambda x: x # Fake gettext function


class feedreader:
    _loop_interval = 4
    _msg_interval = 1.5
    feeds = {}
    run = False
    threads = []

    def __init__(self, bot, config):
        self.bot = bot
        self.store = Storage(bot.store)
        self.lock = threading.RLock()
        self.queue = queue.Queue()

        for feed in config.get("feed", []):
            for subscriber in feed.get("subscriber", []):
                if "jid" not in subscriber:
                    log.error(_("Configuration error - jid attribute of subscriber required."))
                    feed["subscriber"].remove(subscriber)
                    continue
                subscriber["type"] = subscriber.get("type", "groupchat")

            if len(feed.get("subscriber", [])) == 0:
                log.error(_("Configuration error - no subscribers given."))
                continue

            if "url" not in feed:
                log.error(_("Configuration error - url attribute of feed required."))
                continue

            url = feed["url"]
            interval = float(feed.get("interval", 60))
            log.info(_("Scheduling {!r} feed check every {} minutes.").format(url, interval))
            self.feeds[url] = {"interval":interval*60, "subscribers":list(feed["subscriber"])}

        bot.add_event_handler("session_start", self.handle_session_start, threaded=True)
        bot.add_event_handler("disconnected", self.handle_disconnected, threaded=True)
        with self.lock:
             if bot.state.ensure("connected") and bot.session_started_event.isSet():
                 # In case we're already connected, start right away
                self.handle_session_start()

    def handle_session_start(self, data=None):
        with self.lock:
            if self.run:
                # Loops are already started
                return
            self.run = True
            feed_thread = threading.Thread(target=self.feed_loop)
            message_thread = threading.Thread(target=self.message_loop)
            feed_thread.daemon = True
            message_thread.daemon = True
            self.threads.append(feed_thread)
            self.threads.append(message_thread)
            feed_thread.start()
            message_thread.start()

    def handle_disconnected(self, data=None):
        with self.lock:
            self.run = False
            # Join threads
            for thread in self.threads:
                thread.join()
            # Clear message queue
            while not self.queue.empty():
                self.queue.get()
                self.queue.task_done()

    def shutdown(self, bot):
        with self.lock:
            bot.del_event_handler("session_start", self.handle_session_start)
            bot.del_event_handler("disconnected", self.handle_disconnected)
            self.handle_disconnected()

    def feed_loop(self):
        """ The loop that periodically checks feeds """
        log.debug(_("Entering feed loop."))

        for url, feed in self.feeds.items():
            # Initialize feed data
            feed["next_check"] = time.time() + 15
            feed["parser"] = Parser(url)
            feed["items"] = self.store.get(url)

        while self.run:
            now = time.time()
            for url, feed in self.feeds.items():
                if feed["next_check"] > now:
                    continue
                log.debug(_("Checking feed {}.").format(url))
                if not feed["parser"].check():
                    # Error occured
                    feed["next_check"] = now + 300
                    continue
                sent = []
                for item in feed["parser"].items:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    if link in feed["items"]:
                        continue
                    elif title in sent:
                        feed["items"].append(link)
                        self.store.add(url, link)
                        continue
                    log.debug(_("Found new item {!r} in feed {}.").format(title, url))
                    sent.append(title)
                    self.queue.put((url, item))
                feed["next_check"] = now + feed["interval"]
            time.sleep(self._loop_interval)

        log.debug(_("Exiting feed loop."))

    def message_loop(self):
        """ The loop that sends out alerts about new feed items """
        log.debug(_("Entering message loop."))

        msg_times = {}

        while self.run:
            try:
                url, item = self.queue.get(block=False)
                feed = self.feeds[url]
                link = item.get("link", "")
                title = item.get("title", "")
                text = "{}: {}\n{}".format(feed["parser"].channel["title"], title, link)
                subscribers = sorted(feed["subscribers"], key=lambda x: msg_times.get(x["jid"], 0), reverse=True)
                while self.run and len(subscribers) > 0:
                    subscriber = subscribers.pop()
                    jid = subscriber["jid"]
                    if subscriber["type"] == "groupchat" and ("xep_0045" not in self.bot.plugin or jid not in self.bot.plugin["xep_0045"].getJoinedRooms()):
                        log.error(_("Cannot send feed alert, the bot is not in room {!r}.").format(jid))
                        continue
                    time.sleep(max(0, msg_times.get(jid, 0) - time.time()))
                    msg_times[jid] = time.time() + self._msg_interval
                    self.bot.send_message(jid, text, mtype=subscriber["type"])
                if len(subscribers) == 0:
                    # All alerts were sent out
                    feed["items"].append(link)
                    self.store.add(url, link)
            except queue.Empty:
                time.sleep(self._loop_interval)

        log.debug(_("Exiting message loop."))


class Storage:
    def __init__(self, store):
        self.store = store
        self.create_tables()

    def create_tables(self):
        self.store.query("""CREATE TABLE IF NOT EXISTS feeds (
                            feed VARCHAR(256) NOT NULL,
                            item VARCHAR(256) NOT NULL,
                            timestamp INT NOT NULL,
                            PRIMARY KEY (feed, item))""")

    def add(self, feed, item):
        log.debug(_("Storing new item {} in feed {}.").format(item, feed))
        self.store.query("INSERT OR REPLACE INTO feeds (feed, item, timestamp) VALUES(?,?,?)", (feed, item, int(time.time())))

    def get(self, feed):
        for row in self.store.query("SELECT item FROM feeds WHERE feed=? ORDER BY timestamp DESC LIMIT 500, 10000", (feed,)):
            self.store.query("DELETE FROM feeds WHERE feed=? AND item=?", (feed, row["item"]))
        items = []
        for row in self.store.query("SELECT item FROM feeds WHERE feed=?", (feed,)):
            items.append(row["item"])
        return items


class Parser:
    """ Simple feed parser """
    __unescape = HTMLParser().unescape
    items = []

    def __init__(self, url):
        self.url = url
        self.channel = {"title":"", "description":"", "link":self.url}

    def check(self):
        try:
            response = urllib.request.urlopen(self.url, timeout=10)
            xml = ET.parse(response).find("/channel")
            self.items = []
            for element in xml:
                if element.tag == "item":
                    item = {}
                    for item_element in element:
                        item[item_element.tag] = self._unescape(item_element.text).strip()
                    self.items.append(item)
                else:
                    self.channel[element.tag] = self._unescape(element.text).strip()
            return True
        except Exception:
            log.exception(_("Error occured while checking feed {}.").format(self.url))
            return False

    def _unescape(self, text):
        if text is None:
            return ""
        return self.__unescape(text)
