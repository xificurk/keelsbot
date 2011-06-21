"""
    SleekXMPP: The Sleek XMPP Library
    Copyright (C) 2011 Nathanael C. Fritz, Lance J.T. Stout
    This file is part of SleekXMPP.

    See the file LICENSE for copying permission.
"""

import logging
import time

from sleekxmpp import Iq
from sleekxmpp.xmlstream.handler import Callback
from sleekxmpp.xmlstream.matcher import StanzaPath
from sleekxmpp.xmlstream import register_stanza_plugin, JID
from sleekxmpp.plugins.base import base_plugin
from sleekxmpp.plugins.xep_0050 import stanza
from sleekxmpp.plugins.xep_0050 import Command


log = logging.getLogger(__name__)


class xep_0050(base_plugin):

    """
    XEP-0050: Ad-Hoc Commands

    XMPP's Adhoc Commands provides a generic workflow mechanism for
    interacting with applications. The result is similar to menu selections
    and multi-step dialogs in normal desktop applications. Clients do not
    need to know in advance what commands are provided by any particular
    application or agent. While adhoc commands provide similar functionality
    to Jabber-RPC, adhoc commands are used primarily for human interaction.

    Also see <http://xmpp.org/extensions/xep-0050.html>

    Configuration Values:
        threaded -- Indicates if command events should be threaded.
                    Defaults to True.

    Events:
        command_execute  -- Received a command with action="execute"
        command_next     -- Received a command with action="next"
        command_complete -- Received a command with action="complete"
        command_cancel   -- Received a command with action="cancel"

    Attributes:
        threaded -- Indicates if command events should be threaded.
                    Defaults to True.
        commands -- A dictionary mapping JID/node pairs to command
                    names and handlers.
        sessions -- A dictionary or equivalent backend mapping
                    session IDs to dictionaries containing data
                    relevant to a command's session.

    Methods:
        plugin_init       -- Overrides base_plugin.plugin_init
        post_init         -- Overrides base_plugin.post_init
        new_session       -- Return a new session ID.
        prep_handlers     -- Placeholder. May call with a list of handlers
                             to prepare them for use with the session storage
                             backend, if needed.
        set_backend       -- Replace the default session storage with some
                             external storage mechanism, such as a database.
                             The provided backend wrapper must be able to
                             act using the same syntax as a dictionary.
        add_command       -- Add a command for use by external entitites.
        get_commands      -- Retrieve a list of commands provided by a
                             remote agent.
        send_command      -- Send a command request to a remote agent.
        start_command     -- Command user API: initiate a command session
        continue_command  -- Command user API: proceed to the next step
        cancel_command    -- Command user API: cancel a command
        complete_command  -- Command user API: finish a command
        terminate_command -- Command user API: delete a command's session
    """

    def plugin_init(self):
        """Start the XEP-0050 plugin."""
        self.xep = '0050'
        self.description = 'Ad-Hoc Commands'
        self.stanza = stanza

        self.threaded = self.config.get('threaded', True)
        self.commands = {}
        self.sessions = self.config.get('session_db', {})

        self.xmpp.register_handler(
                Callback("Ad-Hoc Execute",
                         StanzaPath('iq@type=set/command'),
                         self._handle_command))

        self.xmpp.register_handler(
                Callback("Ad-Hoc Result",
                         StanzaPath('iq@type=result/command'),
                         self._handle_command_result))

        self.xmpp.register_handler(
                Callback("Ad-Hoc Error",
                         StanzaPath('iq@type=error/command'),
                         self._handle_command_result))

        register_stanza_plugin(Iq, stanza.Command)

        self.xmpp.add_event_handler('command_execute',
                                    self._handle_command_start,
                                    threaded=self.threaded)
        self.xmpp.add_event_handler('command_next',
                                    self._handle_command_next,
                                    threaded=self.threaded)
        self.xmpp.add_event_handler('command_cancel',
                                    self._handle_command_cancel,
                                    threaded=self.threaded)
        self.xmpp.add_event_handler('command_complete',
                                    self._handle_command_complete,
                                    threaded=self.threaded)

    def post_init(self):
        """Handle cross-plugin interactions."""
        base_plugin.post_init(self)
        self.xmpp['xep_0030'].add_feature(Command.namespace)

    def set_backend(self, db):
        """
        Replace the default session storage dictionary with
        a generic, external data storage mechanism.

        The replacement backend must be able to interact through
        the same syntax and interfaces as a normal dictionary.

        Arguments:
            db -- The new session storage mechanism.
        """
        self.sessions = db

    def prep_handlers(self, handlers, **kwargs):
        """
        Prepare a list of functions for use by the backend service.

        Intended to be replaced by the backend service as needed.

        Arguments:
            handlers -- A list of function pointers
            **kwargs -- Any additional parameters required by the backend.
        """
        pass

    # =================================================================
    # Server side (command provider) API

    def add_command(self, jid=None, node=None, name='', handler=None):
        """
        Make a new command available to external entities.

        Access control may be implemented in the provided handler.

        Command workflow is done across a sequence of command handlers. The
        first handler is given the intial Iq stanza of the request in order
        to support access control. Subsequent handlers are given only the
        payload items of the command. All handlers will receive the command's
        session data.

        Arguments:
            jid     -- The JID that will expose the command.
            node    -- The node associated with the command.
            name    -- A human readable name for the command.
            handler -- A function that will generate the response to the
                       initial command request, as well as enforcing any
                       access control policies.
        """
        if jid is None:
            jid = self.xmpp.boundjid
        elif not isinstance(jid, JID):
            jid = JID(jid)
        item_jid = jid.full

        # Client disco uses only the bare JID
        if self.xmpp.is_component:
            jid = jid.full
        else:
            jid = jid.bare

        self.xmpp['xep_0030'].add_identity(category='automation',
                                           itype='command-list',
                                           name='Ad-Hoc commands',
                                           node=Command.namespace,
                                           jid=jid)
        self.xmpp['xep_0030'].add_item(jid=item_jid,
                                       name=name,
                                       node=Command.namespace,
                                       subnode=node,
                                       ijid=jid)
        self.xmpp['xep_0030'].add_identity(category='automation',
                                           itype='command-node',
                                           name=name,
                                           node=node,
                                           jid=jid)
        self.xmpp['xep_0030'].add_feature(Command.namespace, None, jid)

        self.commands[(item_jid, node)] = (name, handler)

    def new_session(self):
        """Return a new session ID."""
        return str(time.time()) + '-' + self.xmpp.new_id()

    def _handle_command(self, iq):
        """Raise command events based on the command action."""
        self.xmpp.event('command_%s' % iq['command']['action'], iq)

    def _handle_command_start(self, iq):
        """
        Process an initial request to execute a command.

        Arguments:
            iq -- The command execution request.
        """
        sessionid = self.new_session()
        node = iq['command']['node']
        key = (iq['to'].full, node)
        name, handler = self.commands.get(key, ('Not found', None))
        if not handler:
            log.debug('Command not found: %s, %s' % (key, self.commands))

        initial_session = {'id': sessionid,
                           'from': iq['from'],
                           'to': iq['to'],
                           'node': node,
                           'payload': None,
                           'interfaces': '',
                           'payload_classes': None,
                           'notes': None,
                           'has_next': False,
                           'allow_complete': False,
                           'allow_prev': False,
                           'past': [],
                           'next': None,
                           'prev': None,
                           'cancel': None}

        session = handler(iq, initial_session)

        self._process_command_response(iq, session)

    def _handle_command_next(self, iq):
        """
        Process a request for the next step in the workflow
        for a command with multiple steps.

        Arguments:
            iq -- The command continuation request.
        """
        sessionid = iq['command']['sessionid']
        session = self.sessions[sessionid]

        handler = session['next']
        interfaces = session['interfaces']
        results = []
        for stanza in iq['command']['substanzas']:
            if stanza.plugin_attrib in interfaces:
                results.append(stanza)
        if len(results) == 1:
            results = results[0]

        session = handler(results, session)

        self._process_command_response(iq, session)

    def _process_command_response(self, iq, session):
        """
        Generate a command reply stanza based on the
        provided session data.

        Arguments:
            iq      -- The command request stanza.
            session -- A dictionary of relevant session data.
        """
        sessionid = session['id']

        payload = session['payload']
        if not isinstance(payload, list):
            payload = [payload]

        session['interfaces'] = [item.plugin_attrib for item in payload]
        session['payload_classes'] = [item.__class__ for item in payload]

        self.sessions[sessionid] = session

        for item in payload:
            register_stanza_plugin(Command, item.__class__, iterable=True)

        iq.reply()
        iq['command']['node'] = session['node']
        iq['command']['sessionid'] = session['id']

        if session['next'] is None:
            iq['command']['actions'] = []
            iq['command']['status'] = 'completed'
        elif session['has_next']:
            actions = ['next']
            if session['allow_complete']:
                actions.append('complete')
            if session['allow_prev']:
                actions.append('prev')
            iq['command']['actions'] = actions
            iq['command']['status'] = 'executing'
        else:
            iq['command']['actions'] = ['complete']
            iq['command']['status'] = 'executing'

        iq['command']['notes'] = session['notes']

        for item in payload:
            iq['command'].append(item)

        iq.send()

    def _handle_command_cancel(self, iq):
        """
        Process a request to cancel a command's execution.

        Arguments:
            iq -- The command cancellation request.
        """
        node = iq['command']['node']
        sessionid = iq['command']['sessionid']
        session = self.sessions[sessionid]
        handler = session['cancel']

        if handler:
            handler(iq, session)

        try:
            del self.sessions[sessionid]
        except:
            pass

        iq.reply()
        iq['command']['node'] = node
        iq['command']['sessionid'] = sessionid
        iq['command']['status'] = 'canceled'
        iq['command']['notes'] = session['notes']
        iq.send()

    def _handle_command_complete(self, iq):
        """
        Process a request to finish the execution of command
        and terminate the workflow.

        All data related to the command session will be removed.

        Arguments:
            iq -- The command completion request.
        """
        node = iq['command']['node']
        sessionid = iq['command']['sessionid']
        session = self.sessions[sessionid]
        handler = session['next']
        interfaces = session['interfaces']
        results = []
        for stanza in iq['command']['substanzas']:
            if stanza.plugin_attrib in interfaces:
                results.append(stanza)
        if len(results) == 1:
            results = results[0]

        if handler:
            handler(results, session)

        iq.reply()
        iq['command']['node'] = node
        iq['command']['sessionid'] = sessionid
        iq['command']['actions'] = []
        iq['command']['status'] = 'completed'
        iq['command']['notes'] = session['notes']
        iq.send()

        del self.sessions[sessionid]


    # =================================================================
    # Client side (command user) API

    def get_commands(self, jid, **kwargs):
        """
        Return a list of commands provided by a given JID.

        Arguments:
            jid      -- The JID to query for commands.
            local    -- If true, then the query is for a JID/node
                        combination handled by this Sleek instance and
                        no stanzas need to be sent.
                        Otherwise, a disco stanza must be sent to the
                        remove JID to retrieve the items.
            ifrom    -- Specifiy the sender's JID.
            block    -- If true, block and wait for the stanzas' reply.
            timeout  -- The time in seconds to block while waiting for
                        a reply. If None, then wait indefinitely.
            callback -- Optional callback to execute when a reply is
                        received instead of blocking and waiting for
                        the reply.
            iterator -- If True, return a result set iterator using
                        the XEP-0059 plugin, if the plugin is loaded.
                        Otherwise the parameter is ignored.
        """
        return self.xmpp['xep_0030'].get_items(jid=jid,
                                               node=Command.namespace,
                                               **kwargs)

    def send_command(self, jid, node, ifrom=None, action='execute',
                    payload=None, sessionid=None, **kwargs):
        """
        Create and send a command stanza, without using the provided
        workflow management APIs.

        Arguments:
            jid       -- The JID to send the command request or result.
            node      -- The node for the command.
            ifrom     -- Specify the sender's JID.
            action    -- May be one of: execute, cancel, complete,
                         or cancel.
            payload   -- Either a list of payload items, or a single
                         payload item such as a data form.
            sessionid -- The current session's ID value.
            block     -- Specify if the send call will block until a
                         response is received, or a timeout occurs.
                         Defaults to True.
            timeout   -- The length of time (in seconds) to wait for a
                         response before exiting the send call
                         if blocking is used. Defaults to
                         sleekxmpp.xmlstream.RESPONSE_TIMEOUT
            callback  -- Optional reference to a stream handler
                         function. Will be executed when a reply
                         stanza is received.
        """
        iq = self.xmpp.Iq()
        iq['type'] = 'set'
        iq['to'] = jid
        if ifrom:
            iq['from'] = ifrom
        iq['command']['node'] = node
        iq['command']['action'] = action
        if sessionid is not None:
            iq['command']['sessionid'] = sessionid
        if payload is not None:
            if not isinstance(payload, list):
                payload = [payload]
            for item in payload:
                iq['command'].append(item)
        return iq.send(**kwargs)

    def start_command(self, jid, node, session, ifrom=None):
        """
        Initiate executing a command provided by a remote agent.

        The workflow provided is always non-blocking.

        The provided session dictionary should contain:
            next  -- A handler for processing the command result.
            error -- A handler for processing any error stanzas
                     generated by the request.

        Arguments:
            jid     -- The JID to send the command request.
            node    -- The node for the desired command.
            session -- A dictionary of relevant session data.
            ifrom   -- Optionally specify the sender's JID.
        """
        session['jid'] = jid
        session['node'] = node
        session['timestamp'] = time.time()
        session['payload'] = None
        iq = self.xmpp.Iq()
        iq['type'] = 'set'
        iq['to'] = jid
        if ifrom:
            iq['from'] = ifrom
            session['from'] = ifrom
        iq['command']['node'] = node
        iq['command']['action'] = 'execute'
        sessionid = 'client:pending_' + iq['id']
        session['id'] = sessionid
        self.sessions[sessionid] = session
        iq.send(block=False)

    def continue_command(self, session):
        """
        Execute the next action of the command.

        Arguments:
            session -- All stored data relevant to the current
                       command session.
        """
        sessionid = 'client:' + session['id']
        self.sessions[sessionid] = session

        self.send_command(session['jid'],
                          session['node'],
                          ifrom=session.get('from', None),
                          action='next',
                          payload=session.get('payload', None),
                          sessionid=session['id'])

    def cancel_command(self, session):
        """
        Cancel the execution of a command.

        Arguments:
            session -- All stored data relevant to the current
                       command session.
        """
        sessionid = 'client:' + session['id']
        self.sessions[sessionid] = session

        self.send_command(session['jid'],
                          session['node'],
                          ifrom=session.get('from', None),
                          action='cancel',
                          payload=session.get('payload', None),
                          sessionid=session['id'])

    def complete_command(self, session):
        """
        Finish the execution of a command workflow.

        Arguments:
            session -- All stored data relevant to the current
                       command session.
        """
        sessionid = 'client:' + session['id']
        self.sessions[sessionid] = session

        self.send_command(session['jid'],
                          session['node'],
                          ifrom=session.get('from', None),
                          action='complete',
                          payload=session.get('payload', None),
                          sessionid=session['id'])

    def terminate_command(self, session):
        """
        Delete a command's session after a command has completed
        or an error has occured.

        Arguments:
            session -- All stored data relevant to the current
                       command session.
        """
        try:
            del self.sessions[session['id']]
        except:
            pass

    def _handle_command_result(self, iq):
        """
        Process the results of a command request.

        Will execute the 'next' handler stored in the session
        data, or the 'error' handler depending on the Iq's type.

        Arguments:
            iq -- The command response.
        """
        sessionid = 'client:' + iq['command']['sessionid']
        pending = False

        if sessionid not in self.sessions:
            pending = True
            pendingid = 'client:pending_' + iq['id']
            if pendingid not in self.sessions:
                return
            sessionid = pendingid

        session = self.sessions[sessionid]
        sessionid = 'client:' + iq['command']['sessionid']
        session['id'] = iq['command']['sessionid']

        self.sessions[sessionid] = session

        if pending:
            del self.sessions[pendingid]

        handler_type = 'next'
        if iq['type'] == 'error':
            handler_type = 'error'
        handler = session.get(handler_type, None)
        if handler:
            handler(iq, session)
        elif iq['type'] == 'error':
            self.terminate_command(session)

        if iq['command']['status']  == 'completed':
            self.terminate_command(session)
