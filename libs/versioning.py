# -*- coding: utf-8 -*-
"""
Storing and comparing version strings.

Functions:
    python_version  --- Return VersionInfo instance with Python version.

Classes:
    VersionInfo     --- Version string container with comparison methods.

"""

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = "Copyright (C) 2009-2010 Petr Morávek"
__license__ = "LGPL 3.0"

__version__ = "0.9.0"

from platform import python_version as _python_version
import re

__all__ = ["python_version",
           "VersionInfo"]


def python_version():
    return VersionInfo(_python_version())


class VersionInfo:
    """
    Version string container with comparison methods.

    Implements methods for comparison with another VersionInfo instance, or str.

    Attributes:
        version         --- List of integers containing version numbers.
        suffix          --- Additional suffix after version numbers (str).
        suffix_version  --- Version number corresponding to the suffix parsed
                            according to VersionInfo._suffix_types.
        major           --- Major version (first value from version attribute).
        minor           --- Minor version (second value from version attribute).

    """

    _version_re = (re.compile("^([0-9]+(\.[0-9]+)*)([^0-9].*)?$"), 1, 3)
    """ (version regular expression, group with version numbers, group with suffix) """

    _suffix_types = [(re.compile("[_.-]?dev(elop)?([0-9]+)?", re.I), 2, -500),
                     (re.compile("[_.-]?a(lpha)?([0-9]+)?", re.I), 2, -400),
                     (re.compile("[_.-]?b(eta)?([0-9]+)?", re.I), 2, -300),
                     (re.compile("[_.-]?pre(view)?([0-9]+)?", re.I), 2, -200),
                     (re.compile("[_.-]?rc([0-9]+)?", re.I), 1, -100),
                     (re.compile("[_.-]?r([0-9]+)?", re.I), 1, 0)]
    """ list of (suffix regular expression, group with version number, base version number) """

    def __init__(self, version):
        """
        Create VersionInfo instance from version string.

        Raise ValueError for an invalid version string.

        Arguments:
            version     --- Version string - should match regular expression
                            contained in VersionInfo._version_re.

        """
        self.version, self.suffix_version, self.suffix = self._parse(version)

    def _parse(self, version):
        version = str(version).strip()
        match = self._version_re[0].match(version)
        if match is None:
            raise ValueError("Invalid version info '{0}'.".format(version))
        else:
            version = []
            for part in match.group(self._version_re[1]).split("."):
                version.append(int(part))
            suffix = ""
            suffix_version = 0
            if match.group(self._version_re[2]) is not None:
                suffix = match.group(self._version_re[2])
                for suffix_type in self._suffix_types:
                    match = suffix_type[0].match(suffix)
                    if match is not None:
                        suffix_version = suffix_type[2]
                        if match.group(suffix_type[1]) is not None:
                            suffix_version += int(match.group(suffix_type[1]))
                        break
        return version, suffix_version, suffix

    @property
    def major(self):
        return self.version[0]

    @property
    def minor(self):
        if len(self.version) > 1:
            return self.version[1]
        else:
            return 0

    def __format__(self, format_spec):
        return format_spec.format(*self.version, suffix=self.suffix)

    def __repr__(self):
        return "VersionInfo('" + str(self) + "')"

    def __str__(self):
        return ".".join((str(part) for part in self.version)) + self.suffix

    def __cmp__(self, other):
        """
        Compare self with other VersionInfo instance or str.

        Return a negative integer if self < other.
        Return zero if self == other.
        Return a positive integer if self > other.

        Arguments:
            other       --- VersionInfo instance or str.

        """
        if not isinstance(other, VersionInfo):
            try:
                other_version, other_suffix_version, other_suffix = self._parse(other)
            except ValueError:
                return NotImplemented
        else:
            other_version = other.version
            other_suffix_version = other.suffix_version
        # Prepare version lists
        self_version = self.version + [0] * max(0, len(other_version) - len(self.version)) + [self.suffix_version]
        other_version = other_version + [0] * max(0, len(self.version) - len(other_version)) + [other_suffix_version]
        # And compare them
        for i in range(0, len(self_version)):
            result = self_version[i] - other_version[i]
            if result != 0:
                return result
        return 0

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __neq__(self, other):
        return self.__cmp__(other) != 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __le__(self, other):
        return self.__cmp__(other) <= 0

    def __gt__(self, other):
        return self.__cmp__(other) > 0

    def __ge__(self, other):
        return self.__cmp__(other) >= 0