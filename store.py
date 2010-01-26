"""
    store.py - Sleekbot's persistant storage module.
    Copyright (C) 2008 Kevin Smith

    SleekBot is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    SleekBot is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this software; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import sqlite3


class store(object):
    def __init__(self, filename):
        self.filename = filename


    def getDb(self):
        """Return a new DB connection"""
        con = sqlite3.connect(self.filename)
        con.row_factory = sqlite3.Row
        return con


    def query(self, query, values=()):
        """Perform query in current database"""
        db = self.getDb()
        result = db.cursor().execute(query, values).fetchall()
        db.commit()
        db.close()
        return result