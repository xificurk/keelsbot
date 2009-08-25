# This Python file uses the following encoding: utf-8
import logging

class basebot(object):
    def __init__(self):
        self.cmd_prefix = '!'
        self.minAccessLevel = 0
        self.lang = 'cs'
        self.clearCommands()
        self.add_event_handler("message", self.handle_message_event, threaded=True)
        self.add_event_handler("groupchat_message", self.handle_message_event, threaded=True)

    def clearCommands(self):
        self.commands = {}
        self.help = {}
        self.polls = []
        self.translations = {}
        self.baseTranslations()

    def baseTranslations(self):
        pass

    def translate(self, name):
        translation = ""
        if name in self.translations and self.lang in self.translations[name]:
            translation = self.translations[name][self.lang]
        else:
            translation = "Undefined translation"
            logging.info("Undefined translation for %s to lang %s." % (name,self.lang))
        return translation

    def getAccessLevel(self, event):
        """ Returns access level of the sender of the event (negative value means bot should ignore this).
            Override this to get better access control.
        """
        if event['type'] == 'groupchat':
            if event['name'] == "" or event['room'] not in self.rooms or self.rooms[event['room']] == event['name']:
                #system, error, or own message
                return -666
        return 0

    def handle_message_event(self, msg):
        print msg.keys()
        level = self.getAccessLevel(msg)
        logging.debug("User lvl: %d, MinAclLevel: %d" % (level, self.minAccessLevel))
        if level < self.minAccessLevel or level < 0:
            return
        command = msg.get('message', '').split(' ', 1)[0]
        if ' ' in msg.get('message', ''):
            args = msg['message'].split(' ', 1)[-1]
        else:
            args = ''
        if command.startswith(self.cmd_prefix):
            if len(self.cmd_prefix):
                command = command.split(self.cmd_prefix, 1)[-1]
            if command in self.commands and self.commands[command]['level'] <= level:
                response = self.commands[command]["pointer"](command, args, msg)
                if msg['type'] == 'groupchat':
                    self.sendMessage("%s" % msg.get('room', ''), "%s: %s" % (msg.get('name', ''), response), mtype=msg.get('type', 'groupchat'))
                else:
                    self.sendMessage("%s/%s" % (msg.get('jid', ''), msg.get('resource', '')), response, mtype=msg.get('type', 'chat'))

    def addHelp(self, topic, title=None, body=None, usage=None):
        if topic is None:
            return
        self.help[topic] = (title, body, usage)

    def addCommand(self, command, pointer, helpTitle = None, helpBody = None, helpUsage = None):
        self.addHelp(command, helpTitle, helpBody, helpUsage)
        level = self.getCommandAccessLevel(command)
        self.commands[command] = {"pointer":pointer,"level":level}

    def getCommandAccessLevel(self, command):
        """ Determine required access level for the command.
            Override this to get better access control.
        """
        return 0

    def addIMCommand(self, command, pointer):
        """ Compatibility with SleekBot plugins.
        """
        self.addCommand(command, pointer)

    def addMUCCommand(self, command, pointer):
        """ Compatibility with SleekBot plugins.
        """
        self.addCommand(command, pointer)
