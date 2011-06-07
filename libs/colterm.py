# -*- coding: utf-8 -*-
"""
Module for managing (colored) terminal input/output.

Variables:
    colors          --- Dictionary with predefined color codes.
    sticky_widgets  --- Mutable sequence of all sticky Widgets.

Functions:
    init_translation    --- Initialize gettext translation.
    use_color           --- Get or set usage of colored output.
    colorize            --- Return message in specified color.
    change_color        --- Change color in specified stream.
    print               --- Extension of built-in print to support colored output.
    change_title        --- Change terminal title.
    move_cursor         --- Move cursor x cells left/right and y cells down/up.
    clear_data          --- Clear part of the screen.
    prompt              --- Prompt user for an input.
    menu                --- Let user chose from a list of options.

Classes:
    ANSI                    --- Factory functions for supported ANSI codes.
    Widget                  --- Widget interface.
    MessageWidget           --- Sticky colored message widget.
    ProgressbarWidget       --- Sticky colored progressbar widget.
    ColoredStreamHandler    --- Stream handler for colored logging.

"""

from __future__ import print_function

__author__ = "Petr Morávek (xificurk@gmail.com)"
__copyright__ = "Copyright (C) 2009-2011 Petr Morávek"
__license__ = "LGPL 3.0"

__version__ = "0.5.1"

from collections import Callable, Container, Iterable, MutableSequence
from gettext import translation
import io
import locale
import logging
import os.path
import platform
import re
import sys
from threading import RLock, Thread
from time import time, sleep

__all__ = ["colors",
           "sticky_widgets",
           "init_translation",
           "use_color",
           "colorize",
           "change_color",
           "print",
           "change_title",
           "move_cursor",
           "clear_data",
           "prompt",
           "menu",
           "ANSI",
           "Widget",
           "MessageWidget",
           "ProgressbarWidget",
           "ColoredStreamHandler"]


_output_lock = RLock()


############################################################
### Python 2.x compatibility.                            ###
############################################################

if sys.version_info[0] < 3:
    input = raw_input

    # Redefine str to return unicode instance
    _str = str
    def str(value):
        if isinstance(value, _str):
            return value.decode("utf-8")
        elif isinstance(value, unicode):
            return value
        else:
            return unicode(_str(value), "utf-8")

    # Fix encoding of strings before writing into streams
    def _fix_encoding(value, stream):
        value = str(value)
        if not isinstance(stream, io.TextIOBase):
            encoding = _get_encoding(stream)
            value = value.encode(encoding)
        return value
else:
    def _fix_encoding(value, stream):
        return str(value)

def _get_encoding(stream):
    if stream.encoding is not None:
        return stream.encoding
    else:
        return locale.getpreferredencoding()


############################################################
### Gettext                                              ###
############################################################

def init_translation(localedir=None, languages=None, fallback=True):
    """
    Initialize gettext translation.

    Arguments:
        localedir   --- Directory with locales (see gettext.translation).
        languages   --- List of languages (see gettext.translation).
        fallback    --- Return a NullTranslations (see gettext.translation).

    """
    global _, gettext, ngettext
    trans = translation("colterm", codeset="utf-8", localedir=localedir, languages=languages, fallback=fallback)
    _ = gettext = trans.gettext
    ngettext = trans.ngettext

init_translation(localedir=os.path.join(os.path.dirname(__file__), "locale"))


############################################################
### Linux/Windows compatibility.                         ###
############################################################

_re_ansi = {}
_re_ansi["title"] = re.compile("\x1b\]0;(.*?)\x07")
_re_ansi["color"] = re.compile("\x1b\[([0-9]+(;[0-9]+)*?)m")
_re_ansi["cursor"] = re.compile("\x1b\[([0-9]*)([ABCD])")
_re_ansi["erase"] = re.compile("\x1b\[([0-2]?)([JK])")

if platform.system() == "Windows":
    from ctypes import windll, byref, Structure, c_short, c_char, c_int


    class COORD(Structure):
        _fields_ = [("X", c_short), ("Y", c_short)]


    class SMALL_RECT(Structure):
        _fields_ = [("Left", c_short), ("Top", c_short),
                    ("Right", c_short), ("Bottom", c_short)]


    class CONSOLE_SCREEN_BUFFER_INFO(Structure):
        _fields_ = [("Size", COORD), ("CursorPosition", COORD), ("Attributes", c_short),
                    ("Window", SMALL_RECT), ("MaximumWindowSize", COORD)]


    class AnsiTerminal(io.TextIOWrapper):
        _win32 = windll.kernel32

        def __init__(self, stream):
            if stream is sys.stdout:
                self._handler = windll.kernel32.GetStdHandle(-11)
            elif stream is sys.stderr:
                self._handler = windll.kernel32.GetStdHandle(-12)
            else:
                raise ValueError("Expected sys.stdout or sys.stderr.")
            if isinstance(stream, io.TextIOWrapper):
                io.TextIOWrapper.__init__(self, stream.buffer,
                                                encoding=_get_encoding(stream),
                                                errors=stream.errors,
                                                line_buffering=stream.line_buffering)
            else:
                file = io.FileIO(stream.fileno(), "w")
                buffered = io.BufferedWriter(file)
                io.TextIOWrapper.__init__(self, buffered,
                                                encoding=_get_encoding(stream),
                                                line_buffering=True)

        def write(self, message):
            for msg in message.split("\x1b"):
                msg = "\x1b" + msg
                for name in _re_ansi:
                    match = _re_ansi[name].match(msg)
                    if match is not None:
                        msg = msg[len(match.group(0)):]
                        getattr(self, "_"+name)(match)
                        break
                msg = msg.replace("\x1b", "")
                if len(msg) > 0:
                    io.TextIOWrapper.write(self, msg)

        def _title(self, match):
            title = str(match.group(1))
            if len(title) > 0:
                self._win32.SetConsoleTitleW(title)

        def _color(self, match):
            bright = None
            foreground = None
            background = None
            for part in set(match.group(1).split(";")):
                part = int(part)
                if part == 0:
                    bright = 0
                    foreground = 7
                    background = 0
                elif part == 22:
                    bright = 0
                elif part == 1:
                    bright = 8
                elif 30 <= part <= 37:
                    foreground = self._rgb2gbr(part - 30)
                elif 40 <= part <= 47:
                    background = self._rgb2gbr(part - 40) * 16
            self.flush()
            if None in (foreground, bright, background):
                sbinfo = self._screen_buffer_info()
                if foreground is None:
                    foreground = sbinfo.Attributes & 7
                if bright is None:
                    bright = sbinfo.Attributes & 8
                if background is None:
                    background = sbinfo.Attributes & 112
            color = foreground | bright | background
            self._win32.SetConsoleTextAttribute(self._handler, color)

        def _cursor(self, match):
            x = 0
            y = 0
            if match.group(1) is None:
                offset = 1
            else:
                offset = int(match.group(1))
            if match.group(2) == "A":
                y = -offset
            elif match.group(2) == "B":
                y = offset
            elif match.group(2) == "C":
                x = offset
            elif match.group(2) == "D":
                x = -offset
            self.flush()
            sbinfo = self._screen_buffer_info()
            x = min(max(0, sbinfo.CursorPosition.X + x), sbinfo.Size.X)
            y = min(max(0, sbinfo.CursorPosition.Y + y), sbinfo.Size.Y)
            self._win32.SetConsoleCursorPosition(self._handler, COORD(x, y))

        def _erase(self, match):
            self.flush()
            sbinfo = self._screen_buffer_info()
            if match.group(2) == "K":
                if match.group(1) == "2":
                    start = COORD(0, sbinfo.CursorPosition.Y)
                    length = sbinfo.Size.X
                elif match.group(1) == "1":
                    start = COORD(0, sbinfo.CursorPosition.Y)
                    length = sbinfo.CursorPosition.X
                else:
                    start = sbinfo.CursorPosition
                    length = sbinfo.Size.X - sbinfo.CursorPosition.X
            elif match.group(2) == "J" and match.group(1) in ("", "1"):
                start = sbinfo.CursorPosition
                length = (sbinfo.Size.X - sbinfo.CursorPosition.X)
                length += (sbinfo.Size.Y - sbinfo.CursorPosition.Y) * sbinfo.Size.X
            else:
                return
            written = c_int()
            self._win32.FillConsoleOutputCharacterA(self._handler, c_char(" "),
                                                    length, start, byref(written))
            self._win32.FillConsoleOutputAttribute(self._handler, sbinfo.Attributes,
                                                    length, start, byref(written))

        def _rgb2gbr(self, color):
            return ((color & 1) << 2) | (color & 2) | ((color & 4) >> 2)

        def _screen_buffer_info(self):
            sbinfo = CONSOLE_SCREEN_BUFFER_INFO()
            self._win32.GetConsoleScreenBufferInfo(self._handler, byref(sbinfo))
            return sbinfo

    if sys.stdout.isatty():
        sys.stdout = AnsiTerminal(sys.stdout)
    if sys.stderr.isatty():
        sys.stderr = AnsiTerminal(sys.stderr)

    def _write(message, stream):
        if not isinstance(stream, AnsiTerminal):
            for _re in _re_ansi.values():
                message = _re.sub("", message)
        else:
            if not use_color():
                message = _re_ansi["color"].sub("", message)
        message = _fix_encoding(message, stream)
        stream.write(message)

else:
    def _write(message, stream):
        if not use_color():
            message = _re_ansi["color"].sub("", message)
        message = _fix_encoding(message, stream)
        stream.write(message)

def _flush(stream):
    if hasattr(stream, "flush"):
        stream.flush()


############################################################
### ANSI codes factories.                                ###
############################################################

class ANSI:
    """
    Factory functions for supported ANSI codes.

    Methods:
        color       --- Return ANSI SGR code.
        title       --- Return ANSI code for changing terminal title.
        move_cursor --- Return ANSI code for moving cursor x cells left/right
                        and y cells down/up.
        clear_data  --- Return ANSI code for clearing part of the screen.

    """

    _csi = "\x1b["
    _colors = {"R":1, "G":2, "B":4}

    @classmethod
    def color(cls, foreground=None, bright=None, background=None):
        """
        Return ANSI SGR code.
        If any of keyworded arguments is omitted, the corresponding feature is left
        unchanged.

        Keyworded arguments:
            foreground  --- Foreground color - Container with combination of 'R', 'G','B'.
            bright      --- Use bright/bold font - boolean.
            background  --- Background color - Container with combination of 'R', 'G', 'B'.

        """
        color_parts = []
        if bright is not None:
            if bright:
                color_parts.append("1")
            else:
                color_parts.append("22")
        if foreground is not None:
            part = 30
            for color in cls._colors:
                if color in foreground:
                    part += cls._colors[color]
            color_parts.append(str(part))
        if background is not None:
            part = 40
            for color in cls._colors:
                if color in background:
                    part += cls._colors[color]
            color_parts.append(str(part))
        if len(color_parts) > 0:
            return cls._csi + ";".join(color_parts) + "m"
        else:
            return ""

    @classmethod
    def title(cls, title):
        """
        Return ANSI code for changing terminal title.

        Arguments:
            title       --- String to display as terminal title.

        """
        return str("\x1b]0;{0}\x07").format(str(title))

    @classmethod
    def move_cursor(cls, x=0, y=0):
        """
        Return ANSI code for moving cursor x cells left/right and y cells down/up.

        Keyworded arguments:
            x           --- Number of cells to move cursor left (negative x) or
                            right (positive x).
            y           --- Number of cells to move cursor up (negative y) or
                            down (positive y).

        """
        x = int(x)
        y = int(y)
        code = ""
        if x < 0:
            code += cls._csi + "{0}D".format(int(-x))
        elif x > 0:
            code += cls._csi + "{0}C".format(int(x))
        if y < 0:
            code += cls._csi + "{0}A".format(int(-y))
        elif y > 0:
            code += cls._csi + "{0}B".format(int(y))
        return code

    @classmethod
    def clear_data(cls, mode):
        """
        Return ANSI code for clearing part of the screen.

        Arguments:
            mode        --- What data should be cleared, one of 'screen_end',
                            'line_end', 'line_start', 'line'.

        """
        if mode == "screen_end":
            return cls._csi + "J"
        elif mode == "line_end":
            return cls._csi + "K"
        elif mode == "line_start":
            return cls._csi + "1K"
        elif mode == "line":
            return cls._csi + "2K"
        else:
            return ""


############################################################
### Color management through ANSI SGR codes.             ###
############################################################

colors = {}
""" Dictionary with predefined color codes. """
colors["reset"] = ANSI._csi + "0;37;40m"
colors["notset"] = ANSI.color("GB", False, "")
colors["debug"] = ANSI.color("RB", False, "")
colors["info"] = ANSI.color("RGB", True, "")
colors["warning"] = ANSI.color("RG", True, "")
colors["error"] = ANSI.color("R", True, "")
colors["critical"] = ANSI.color("RG", True, "R")
colors["prompt_question"] = ANSI.color(bright=True)
colors["prompt_error"] = ANSI.color("R")
colors["menu_header"] = ANSI.color(bright=True)
colors["progressbar"] = ""
colors["header"] = ANSI.color("G", True, "")

_use_color = False

def use_color(enabled=None):
    """
    Get or set usage of colored output.

    Keyworded arguments:
        enabled     --- If None return current status, else set status.

    """
    global _use_color
    if enabled is None:
        return _use_color
    else:
        enabled = bool(enabled)
        if enabled ^ _use_color:
            _use_color = True
            with _output_lock:
                if enabled:
                    change = colors["reset"]
                else:
                    change = "\x1b[0m"
                if not (sys.stdout.isatty() and sys.stderr.isatty()):
                    change_out = change + "\n"
                else:
                    change_out = change
                change_err = change + "\n"
                sticky_widgets.clear()
                _write(str(change_out), sys.stdout)
                _write(str(change_err), sys.stderr)
                _flush(sys.stdout)
                _flush(sys.stderr)
                _use_color = enabled
                sticky_widgets.output()

def colorize(message, color):
    """
    Return message in specified color.

    Arguments:
        message     --- String message.
        color       --- Color name from colors dictionary or color code.

    """
    if len(color) <= 0 or len(message) <= 0:
        return message
    if color in colors:
        color = colors[color]
    end = ""
    if message.endswith("\n"):
        message = message[:-1]
        end = "\n"
    return str("{0}{1}{2}{3}").format(str(color), str(message), colors["reset"], end)

def change_color(color="", stream=None):
    """
    Change color of specified stream.

    If use_color is False, ignore this call.

    Keyworded arguments:
        color       --- Color name from colors dictionary or color code.
        stream      --- Stream where the change should be performed (None
                        defaults to sys.stdout).

    """
    if stream is None:
        stream = sys.stdout
    if not use_color() or len(color) <= 0:
        return
    if color in colors:
        color = colors[color]
    sticky_widgets.refresh(stream, color)

def print(*objects, **kwargs):
    """
    Extension of built-in print to support colored output.

    Arguments:
        objects     --- Objects to print.

    Keyworded arguments:
        sep         --- Separator between objects (default ' ').
        end         --- String to append at the end (default '\n').
        file        --- Stream where the result should be written (None
                        defaults to sys.stdout).
        color       --- Color name from colors dictionary or color code.

    """
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    stream = kwargs.get("file", sys.stdout)
    color = kwargs.get("color", "")
    message = str(sep).join((str(o) for o in objects)) + str(end)
    if use_color():
        message = colorize(message, color)
    sticky_widgets.refresh(stream, message)


############################################################
### Other supported ANSI commands.                       ###
############################################################

def change_title(title, stream=None):
    """
    Change terminal title.

    Arguments:
        title       --- Title text.

    Keyworded arguments:
        stream      --- Stream where the change should be written (None
                        defaults to sys.stdout or sys.stderr depending on which
                        one is atty).

    """
    if stream is None:
        if sys.stdout.isatty():
            stream = sys.stdout
        else:
            stream = sys.stderr
    message = ANSI.title(title)
    if len(message) > 0:
        with _output_lock:
            _write(str(message), stream)
            _flush(stream)

def move_cursor(x=0, y=0, stream=None):
    """
    Move cursor x cells left/right and y cells down/up.

    If the cursor is already at the edge of the screen, this has no effect.

    Keyworded arguments:
        x           --- Number of cells to move cursor left (negative x) or
                        right (positive x).
        y           --- Number of cells to move cursor up (negative y) or
                        down (positive y).
        stream      --- Stream where the change should be performed (None
                        defaults to sys.stdout).

    """
    if stream is None:
        stream = sys.stdout
    message = ANSI.move_cursor(x, y)
    if len(message) > 0:
        sticky_widgets.refresh(stream, message)

def clear_data(mode, stream=None):
    """
    Clear part of the screen.

    Arguments:
        mode        --- What data should be cleared, one of 'screen_end',
                        'line_end', 'line_start', 'line'.

    Keyworded arguments:
        stream      --- Stream where the change should be performed (None
                        defaults to sys.stdout).

    """
    if stream is None:
        stream = sys.stdout
    message = ANSI.clear_data(mode)
    if len(message) > 0:
        sticky_widgets.refresh(stream, message)


############################################################
### Sticky widgets.                                      ###
############################################################

class Widget:
    """
    Widget interface.

    Attributes:
        attached    --- Is the widget in sticky_widgets?

    """

    @property
    def attached(self):
        """ Is the widget in sticky_widgets? """
        return self in sticky_widgets

    _line_count = 0
    """ Number of lines in the content. """

    _content = ""
    """ Content to output. """

    def _startup(self):
        """ Called when the widget is added to sticky_widgets. """
        if self.attached:
            raise RuntimeError("Widget is already attached.")

    def _shutdown(self):
        """ Called when the widget is removed from sticky_widgets. Return shutdown message. """
        return ""


class MessageWidget(Widget):
    """
    Sticky colored message widget.

    """

    def __init__(self, message, color=""):
        """
        Arguments:
            message     --- String message to display.

        Keyworder arguments:
            color       --- Color to use for displaying the message.

        """
        if not message.endswith("\n"):
            message += "\n"
        self._content = colorize(message, color)
        self._line_count = self._content.count("\n")


class ProgressbarWidget(Widget):
    """
    Sticky colored progressbar widget.

    Attributes:
        chars       --- Tuple of characters to use for progressbar (set in __init__
                        on depending on sticky_widgets.stream.encoding).
        colors      --- Dictionary of {min_percent: color} of colors to use to
                        mark progress.

    Methods:
        inc         --- Increment counter, update message and redraw progressbar.

    """

    colors = {}
    colors[0] = ANSI.color("R", True)
    colors[50] = ANSI.color("RG", True)
    colors[75] = ANSI.color("G", True)

    def __init__(self, total, header="", eta=False, width=60):
        """
        Arguments:
            total       --- Total number of steps to finish.

        Keyworded arguments:
            header      --- Header of progressbar.
            eta         --- Display ETA - boolean.
            width       --- Width of progressbar

        """
        total = int(total)
        if total <= 0:
            raise ValueError("Total number of steps must be greater than zero.")
        self._total = total
        self._step = 0
        header = header.strip("\n")
        if len(header) > 0:
            header += "\n"
        self._header = colorize(header, "header")
        self._width = max(0, int(width))
        self._message = self._message_old = str("Starting...\n")
        encoding = _get_encoding(sticky_widgets.stream).lower().replace("_", "-")
        if encoding in ("utf-8", "utf-16", "utf-32"):
            self.chars = (" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█")
        elif encoding in ("cp850", "cp852"):
            self.chars = (" ", "░", "▒", "▓", "█")
        else:
            self.chars = (" ", "-", "=", "#")
        self._eta = bool(eta)

    def inc(self, message=""):
        """
        Increment counter, update message and redraw progressbar.

        Keyworded arguments:
            message     --- Message to display.

        """
        if not self.attached:
            raise RuntimeError("Tried to increment progressbar that is not attached to sticky_widgets.")
        with _output_lock:
            self._step += 1
            message = str(message).strip("\n")
            if len(message) > 0:
                message += "\n"
            self._message = message
            if self._eta:
                self._time_step = time()
            sticky_widgets.refresh()
            if self._step >= self._total:
                sticky_widgets.remove(self)

    @property
    def _line_count(self):
        """ Number of lines in the content. """
        lines = 1 + self._header.count("\n") + self._message_old.count("\n")
        self._message_old = self._message
        return lines

    @property
    def _content(self):
        """ Content to output. """
        percent = min(float(self._step) / self._total, 1.0) * 100.0
        color = ""
        for min_percent in sorted(self.colors.keys(), reverse=True):
            if percent >= min_percent:
                color = self.colors[min_percent]
                break
        char_count = percent / 100.0 * self._width
        progressbar = self.chars[-1] * int(char_count)
        if percent < 100.0 and self._width >= 1:
            char_current = int((char_count - int(char_count)) * len(self.chars))
            progressbar += self.chars[char_current] + self.chars[0] * (self._width - 1 - int(char_count))
        progressbar = str("{2}{0:5.1f}%{4} |{3}{1}{4}|").format(percent, str(progressbar), color,
                                                      colors["progressbar"], colors["reset"])

        if self._eta:
            self._time_update = time()
            if self._step > 0:
                self._guess_eta()
                eta = self._format_time(self._eta_time)
            else:
                eta = "--:--:--"
            progressbar += str(" {1}{0}{2}").format(eta, color, colors["reset"])
        progressbar += "\n"
        return self._header + progressbar + self._message

    def _startup(self):
        """ Called when the widget is added to sticky_widgets. """
        Widget._startup(self)
        self._time_start = time()
        if self._eta:
            self._time_update = self._time_start
            self._eta_time = 1
            t = Thread(target=self._eta_loop)
            t.daemon = True
            t.start()

    def _shutdown(self):
        """ Called when the widget is removed from sticky_widgets. Return shutdown message. """
        if len(self._header) > 0:
            message = self._header.strip("\n")
            if self._eta:
                elapsed = self._format_time(time() - self._time_start)
                message += str(" {0} {1}").format(str(_("finished in")), elapsed)
            return message + "\n"
        else:
            return ""

    def _guess_eta(self):
        time_last = time() - self._time_step
        time_step = (self._time_step - self._time_start) / self._step
        time_step += max(0, (time_last - time_step) / self._step)
        self._eta_time = time_step * (self._total - self._step) - time_last

    def _format_time(self, secs):
        secs = float(secs)
        hours = int(secs / 3600)
        secs -= hours * 3600
        mins = int(secs / 60)
        secs = int(secs - mins * 60)
        return "{0:02d}:{1:02d}:{2:02d}".format(hours, mins, secs)

    def _eta_loop(self):
        sleep(2)
        while self._step <= 0 and self.attached:
            sleep(2)
        while self._step < self._total and self.attached:
            sleep_time = min(30, max(1, self._eta_time / 60))
            sleep(max(0, sleep_time - time() + self._time_update))
            if time() - self._time_update >= sleep_time:
                sticky_widgets.refresh()


class _StickyWidgetsContainer(MutableSequence):
    _stream = sys.stdout
    _cleared = True

    def __init__(self):
        self._widgets = []

    def __len__(self):
        return self._widgets.__len__()

    def __iter__(self):
        return self._widgets.__iter__()

    def __getitem__(self, index):
        return self._widgets.__getitem__(index)

    def __setitem__(self, index, value):
        if not isinstance(value, Widget):
            raise TypeError("Expected Widget instance.")
        with _output_lock:
            if self.enabled():
                message = self._prepare_clear()
            value._startup()
            self._widgets.__setitem__(index, value)
            if self.enabled():
                message += self._prepare_output()
                _write(str(message), self._stream)
                _flush(self._stream)

    def insert(self, index, value):
        if not isinstance(value, Widget):
            raise TypeError("Expected Widget instance.")
        with _output_lock:
            if self.enabled():
                message = self._prepare_clear()
            value._startup()
            self._widgets.insert(index, value)
            if self.enabled():
                message += self._prepare_output()
                _write(str(message), self._stream)
                _flush(self._stream)

    def __delitem__(self, index):
        with _output_lock:
            message = ""
            if self.enabled():
                message = self._prepare_clear()
            message += self._widgets.pop(index)._shutdown()
            if self.enabled():
                message += self._prepare_output()
            if len(message) > 0:
                _write(str(message), self._stream)
                _flush(self._stream)

    @property
    def stream(self):
        return self._stream

    def enabled(self, stream=None):
        return self._stream.isatty() and (stream is None or
               (stream in (sys.stdout, sys.stderr) and stream.isatty()))

    def set_stdout(self):
        with _output_lock:
            self.clear()
            self._stream = sys.stdout
            self.output()
        return self.enabled()

    def set_stderr(self):
        with _output_lock:
            self.clear()
            self._stream = sys.stderr
            self.output()
        return self.enabled()

    def _prepare_clear(self):
        if len(self._widgets) <= 0 or self._cleared:
            return ""
        self._cleared = True
        lines = 0
        for widget in self._widgets:
            lines += widget._line_count
        return "\r" + ANSI.move_cursor(y=-lines) + ANSI.clear_data("screen_end")

    def _prepare_output(self):
        if len(self._widgets) <= 0:
            return ""
        self._cleared = False
        message = colors["reset"]
        for widget in self._widgets:
            message += widget._content
        return message

    def clear(self, stream=None):
        with _output_lock:
            if self.enabled(stream):
                message = self._prepare_clear()
                if len(message) > 0:
                    _write(str(message), self._stream)
                    _flush(self._stream)

    def output(self, stream=None):
        with _output_lock:
            if self.enabled(stream):
                message = self._prepare_output()
                if len(message) > 0:
                    _write(str(message), self._stream)
                    _flush(self._stream)

    def refresh(self, stream=None, message=""):
        with _output_lock:
            message = str(message)
            if self.enabled() and stream in (None, self._stream):
                message = self._prepare_clear() + message + self._prepare_output()
                if len(message) > 0:
                    _write(str(message), self._stream)
                    _flush(self._stream)
            elif stream is not None:
                self.clear(stream)
                if len(message) > 0:
                    _write(message, stream)
                    _flush(stream)
                self.output(stream)


sticky_widgets = _StickyWidgetsContainer()
"""
Mutable sequence of all sticky Widgets.
"""


############################################################
### User input.                                          ###
############################################################

_indentation = "  "

def prompt(question, indent_lvl=0, default=None, validate=None):
    """
    Prompt user for an input.

    If input is empty, use default value (if not None), then check validity of
    the value and finally return the result.

    Arguments:
        question    --- Prompt text.

    Keyworded arguments:
        indent_lvl  --- Level of indentation.
        default     --- If no input is provided and default is not None, use it.
        validate    --- Validation rule:
                        - Iterable Container: Input must be one of the values;
                          '{CHOICES}' in question string will be replaced by
                          list of values in validate.
                        - Callable: Call the function with input as argument
                          expecting to return error message or None.
                        - 'BOOLEAN': Try to match input to yes/no answer, valid
                          result is then a boolean value.
                        - 'INTEGER': Check input by isdigit(), valid result is
                          then return an integer.
                        - 'DECIMAL': Check if input is decimal number, valid
                          result is then float.
                        - 'ALNUM': Check input by isalnum().
                        - not None: Check if input is non-empty.
                        - None: Do not check input.

    """
    with _output_lock:
        sticky_widgets.clear(sys.stdout)
        message = str("{0}{1} ").format(_indentation * indent_lvl, str(question))
        if default is not None:
            message += str("[{0}] ").format(str(default))
        if isinstance(validate, Iterable) and isinstance(validate, Container):
            choices = str(", ").join((str(v) for v in validate))
            message = message.format(CHOICES=choices)
        if use_color():
            message = colorize(message, "prompt_question")
        _write(message, sys.stdout)
        _flush(sys.stdout)
        value = input()
        if len(value) == 0 and default is not None:
            value = default
        error = None
        if isinstance(validate, Iterable) and isinstance(validate, Container):
            if value not in validate:
                error = str(_("Please, input a value from {0}.")).format(choices)
        elif isinstance(validate, Callable):
            error = validate(value)
        elif validate == "BOOLEAN":
            if value.lower() in (_("y"), _("yes")):
                value = True
            elif value.lower() in (_("n"), _("no")):
                value = False
            else:
                error = _("Please, answer yes/no (y/n).")
        elif validate == "INTEGER":
            if value.isdigit():
                value = int(value)
            else:
                error = _("Use only digits, please.")
        elif validate == "DECIMAL":
            if re.match("^-?[0-9]+\.?[0-9]*$", value) is not None:
                value = float(value)
            else:
                error = _("Please, input a decimal number.")
        elif validate == "ALNUM":
            if not value.isalnum():
                error = _("Please, use only alpha-numeric characters.")
        elif validate is not None:
            if len(value) == 0:
                error = _("Please, input a non-empty string.")
        if error is not None:
            message = str("{0}{1}: {2}\n").format(_indentation * indent_lvl, str(_("ERROR")), str(error))
            if use_color():
                message = colorize(message, "prompt_error")
            _write(message, sys.stdout)
            return prompt(question, indent_lvl, default, validate)
        sticky_widgets.output(sys.stdout)
    return value

def _menu_validator(choices, value):
    if not (value in choices or (value.isdigit() and int(value) >= 1 and int(value) <= len(choices))):
        return _("Please, chose an option from the list - input a number, or a full text of the desired option.")
    else:
        return None

def menu(header, choices, indent_lvl=0, default=None):
    """
    Let user chose from a list of options.

    Arguments:
        header      --- Header text.
        choices     --- Iterable of choices.

    Keyworded arguments:
        indent_lvl  --- Level of indentation.
        default     --- Default option to chose.

    """
    with _output_lock:
        sticky_widgets.clear(sys.stdout)
        message = str("{0}{1}\n").format(_indentation * indent_lvl, str(header))
        if use_color():
            message = colorize(message, "menu_header")
        _write(message, sys.stdout)
        choices = tuple(choices)
        if len(choices) < 1:
            raise ValueError("Choices form an empty list.")
        for i in range(len(choices)):
            message = str("{0}{1:2d}) {2}\n").format(_indentation * (indent_lvl+1), i+1, str(choices[i]))
            _write(message, sys.stdout)
        value = prompt(_("Select") + ":", indent_lvl+1, default, lambda val: _menu_validator(choices, val))
    if value.isdigit() and int(value) >= 1 and int(value) <= len(choices):
        return choices[int(value)-1]
    else:
        return value


############################################################
### Logging.                                             ###
############################################################

class ColoredStreamHandler(logging.StreamHandler):
    """
    Stream handler for colored logging.

    Output colored logging records to the stream.

    Subclass attributes:
        colors      --- Dictionary of custom color codes for logging levels.

    Subclass methods:
        emit        --- Override the emit method of logging.StreamHandler to
                        provide colored (depending on record.levelname) and
                        formatted output.

    """

    def __init__(self, stream=None, fmt="%(levelname)-8s %(name)-15s %(message)s", datefmt=None, colors={}):
        """
        Create a subclass of logging.StreamHandler for specified stream and
        install logging.Formatter with provided fmt and datefmt.

        Keyworded arguments:
            stream      --- Stream to use for logging.StreamHandler initiation.
            fmt         --- Format for logging.Formatter initiation.
            datefmt     --- Date format for logging.Formatter initiation.
            colors      --- Dictionary of custom color codes for logging levels.

        """
        logging.StreamHandler.__init__(self, stream)
        self.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
        self.colors = dict(colors)

    def _get_record_color(self, record):
        if not use_color():
            return ""
        try:
            return self._get_color(record.levelname.lower())
        except KeyError:
            try:
                if record.levelno >= 50:
                    return self._get_color("critical")
                elif record.levelno >= 40:
                    return self._get_color("error")
                elif record.levelno >= 30:
                    return self._get_color("warning")
                elif record.levelno >= 20:
                    return self._get_color("info")
                elif record.levelno >= 10:
                    return self._get_color("debug")
                else:
                    return self._get_color("notset")
            except KeyError:
                return ""

    def _get_color(self, color_name):
        if color_name in self.colors:
            return self.colors[color_name]
        else:
            return colors[color_name]

    def emit(self, record):
        """
        Emit formatted (and colored if enabled) record to the stream.

        If the record has lvelno >= 50, raise SystemExit(1).

        Arguments:
            record      --- Logging record to emit.

        """
        try:
            message = self.format(record)
            color = self._get_record_color(record)
            print(message, file=self.stream, color=color)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            pass
        if record.levelno >= 50:
            raise SystemExit(1)