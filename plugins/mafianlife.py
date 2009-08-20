# This Python file uses the following encoding: utf-8
"""
    mafianlife.py - A plugin for returning links to comics from MaFian liFe.
    Copyright (C) 2009 Petr Morávek

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

class mafianlife(object):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.about = u"'MafianLife' vrací odkaz na komiks z MaFian liFe.\nAutor: Petr Morávek"
        self.bot.addCommand('mafian', self.handle_mafian, 'Strip MaFian liFe', u"Vrací odkaz na strip z MaFian liFe", u'mafian [číslo stripu]')

    def handle_mafian(self, command, args, msg):
        if args == "":
            return u"No tak se nestyď, řekni mi číslo stripu, který chceš ;-)"
        nr = int(args)
        return u"http://www-ucjf.troja.mff.cuni.cz/scheirich/comics/mff_life_%.2d.jpg" % nr