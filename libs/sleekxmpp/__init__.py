"""
    SleekXMPP: The Sleek XMPP Library
    Copyright (C) 2010  Nathanael C. Fritz
    This file is part of SleekXMPP.

    See the file LICENSE for copying permission.
"""

from sleekxmpp.basexmpp import BaseXMPP
from sleekxmpp.clientxmpp import ClientXMPP
from sleekxmpp.componentxmpp import ComponentXMPP
from sleekxmpp.stanza import Message, Presence, Iq
from sleekxmpp.xmlstream.handler import *
from sleekxmpp.xmlstream import XMLStream, RestartStream
from sleekxmpp.xmlstream.matcher import *
from sleekxmpp.xmlstream.stanzabase import StanzaBase, ET

__version__ = '1.0beta5'
__version_info__ = (1, 0, 0, 'beta5', 0)
