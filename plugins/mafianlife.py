# -*- coding: utf-8 -*-
"""
    plugins/mafianlife.py - A plugin for returning links to comics
    from MaFian liFe.
    Copyright (C) 2009-2010 Petr Morávek

    This file is part of KeelsBot.

    Keelsbot is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    KeelsBot is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""


class mafianlife(object):
    def __init__(self, bot, config):
        self.about = "'MafianLife' vrací odkaz na komiks z MaFian liFe.\nAutor: Petr Morávek"
        bot.addCommand("mafian", self.strip, "Strip MaFian liFe", "Vrací odkaz na strip z MaFian liFe", "mafian [číslo stripu]")

    def strip(self, command, args, msg):
        if args == "":
            return "No tak se nestyď, řekni mi číslo stripu, který chceš ;-)"
        nr = int(args)
        return "http://www-ucjf.troja.mff.cuni.cz/scheirich/comics/mff_life_{0:02d}.jpg".format(nr)
