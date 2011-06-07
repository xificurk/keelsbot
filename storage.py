# -*- coding: utf-8 -*-
"""
Module for accessing persistent sqlite3 storage.

Classes:
    Storage     --- Sqlite3 database storage.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = ["Copyright (C) 2008 Kevin Smith",
                 "Copyright (C) 2009-2011 Petr Morávek"]
__license__ = "GPL 3.0"
__version__ = "0.5.0"

import sqlite3


class Storage:
    """
    Sqlite3 database storage.

    Methods:
        get_db  --- Get database connection instance.
        query   --- Return ANSI code for changing terminal title.

    """
    def __init__(self, filename):
        """
        Arguments:
            filename    --- Path to sqlite3 file.

        """
        self._filename = filename


    def get_db(self):
        """
        Get database connection instance.

        """
        con = sqlite3.connect(self._filename)
        con.row_factory = sqlite3.Row
        return con


    def query(self, query, values=()):
        """
        Perform query in current database.

        Arguments:
            query   --- SQL query.

        Keyworded arguments:
            values  --- Values to substitute in the query.

        """
        db = self.get_db()
        result = db.cursor().execute(query, values).fetchall()
        db.commit()
        db.close()
        return result