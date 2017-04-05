#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create GUI frontends for your programs, .e.g. desktops.

import cursed

Cite
----
- Based on GitHub's MrMattBusby/templates/template_curses.py
  - Please backport any relevent template changes via fork

TODO
----
- desktop's init should clear all and call all sub's inits
- properties for curses subwin calls
- config file
  - log file
  - colors

NOTE
----
- Check LOGFOLDER for runtime logs since printing to stdout/err is not possible
  with curses initialized
- Origin 0,0 is upper left corner, +y is down, +x is right
- Setting the background only does so for any changed part of a window and
  point to the +x right of that update

WARNING
-------
- Vte (default) terminal emulators only support mouse click input within
  223 character pixel range (this is about 3/4 a screen at 1920x1200 rez)

"""

# SYSTEM
from datetime import datetime
NOW = datetime.today()
import time
import curses
# import curses.ascii
# import curses.textpad
import logging
from logging.handlers import RotatingFileHandler
import os
import pwd
import sys

# EXTERNAL
try:
    import pudb as pdb
except ImportError:
    import pdb

## GLOBALS
#
NONBLOCKING = True  # Getch blocking
NONBLOCKING_TIMEOUT = 5  # 0 # Getch, ms
SLEEPTIME = .002  # Sleep time after update, sec
MOUSEINTERVAL = 150  # Click time, ms

# Logging
LOGFOLDER = ["/var/log/", "/var/tmp/", "/usr/tmp/", "/tmp/"]
LOGFILE = "curses-py.log"
LOGMAX = 10 * 1024**2
FMAT = r'%(asctime)s.%(msecs)-3d | ' + \
        r'%(levelname)-8s | ' + \
        r'{0:12s} | ' + \
        r'%(filename)-15s | ' + \
        r'%(lineno)-5d | ' + \
        r'%(funcName)-20s | ' + \
        r'%(message)s'
FTIME = r'%y-%m-%d %H:%M:%S'
FORMATTER = logging.Formatter(FMAT.format(pwd.getpwuid(os.getuid())[0]), FTIME)
LOG = logging.getLogger("curses-py")
LOG.setLevel(1)

logging.addLevelName(10, '   DBUG ')
logging.addLevelName(20, '   INFO ')
logging.addLevelName(30, '  !WARN ')
logging.addLevelName(40, ' !!ERRR ')
logging.addLevelName(50, '!!!CRIT ')
for folder in LOGFOLDER:
    filename = os.path.join(folder, LOGFILE)
    try:
        fh = RotatingFileHandler(filename, maxBytes=LOGMAX, backupCount=1)
    except:
        continue
    else:
        fh.setFormatter(FORMATTER)
        LOG.addHandler(fh)
        break
LOG.info("***** {} started at {} *****".format(__file__, NOW))

# Mouse click events
SGL_CLICKS = (curses.BUTTON1_CLICKED, curses.BUTTON1_RELEASED)
DBL_CLICKS = (curses.BUTTON1_DOUBLE_CLICKED, curses.BUTTON1_TRIPLE_CLICKED)

# Colors, 16 colors can be active at once including 'default'
CLRS = {
        'default' : -0x01,
        'dgray'   :  0x00,
        'red'     :  0x01,
        'green'   :  0x02,
        'cyan'    :  0x0e,
        #'magenta' :  0x0d,
        'black'   :  0x10,
        #'navy'    :  0x13,
        'blue'    :  0x15,
        'indigo'  :  0x36,
        #'sage'    :  0x41,
        #'lime'    :  0x52,
        'brown'   :  0x5e,
        'violet'  :  0x81,
        #'sky'     :  0x9f,
        #'dorange' :  0xc4,
        #'dpink'   :  0xc8,
        'orange'  :  0xca,
        #'pink'    :  0xd5,
        'yellow'  :  0xe2,
        'cream'   :  0xe5, 
        'white'   :  0xe7,
        'gray'    :  0xf1,
        'lgray'   :  0xfa,
       }

# Text attributes
ATTRS = {'bold'  : curses.A_BOLD,
         'dim'   : curses.A_DIM,
         'invis' : curses.A_INVIS,
         'norm'  : curses.A_NORMAL,
         'rev'   : curses.A_REVERSE,
         'uline' : curses.A_UNDERLINE
        }

# Color pair attributes, e.g. PAIRS[(fg,bg)]
PAIRS = {}

## CLASSES
#
class Window(object):
    """Curses subwindows."""

    _z_top = 0
    has_titlebar = False
    has_menubar = False
    has_border = False
    has_shadows = False
    backgroundch = ' '

    def __init__(self, scr=None, y=10, x=10, ysize=10, xsize=20, fg='dgray',
            bg='cream', id=None, title=None, **kwargs):

        self._id = id if id else hash(time.time())
        self.title = title if title else ''

        # Subwins
        self.scr = scr
        self.titlebar = None
        self.menubar = None

        # Hidden
        self.active = True

        # Init values
        self.y = y
        self.x = x
        if ysize < 1:
            LOG.warn("{}.ysize minimum is 1".format(type(self).__name__))
            self.ysize = 1
        else:
            self.ysize = ysize
        if xsize < 1:
            LOG.warn("{}.xsize minimum is 1".format(type(self).__name__))
            self.xsize = 1
        else:
            self.xsize = xsize
        self._fg = fg
        self._bg = bg

        # Z level
        self._z = Window._z_top

        # Latched warnings
        self._on_click_warn = False
        self._on_init_warn = False
        self._on_key_warn = False
        self._on_redraw_warn = False

    def __repr__(self):
        return "{}: {}(".format(type(self).__name__, self.__class__.__name__) + ", ".join(["{}={}".format(k, v) for k, v in self.__dict__.items()]) + ")"

    def _on_click(self, my, mx, click):
        self.on_click(my, mx, click) # TODO How to translate into y/x for sunwin coordinates?

    def _on_init(self):
        self.scr.clear()
        self.scr.bkgd(self.backgroundch, PAIRS[(self._fg, self._bg)])
        self.on_init()
        self.scr.redrawwin()  # Touch whole window, needed if bkgd changes

    def _on_key(self, getch):
        self.on_key(getch)

    def _on_redraw(self):
        try:
            self.on_redraw()
        except curses.error:
            LOG.error("{} is writing to bad area".format(type(self).__name__))
        # self.scr.vline(0, 223, '|', ymax) <-- End of mouse support

    @property
    def _ymax(self):
        if self.active:
            return self.scr.getmaxyx()[0]
        else:
            return 0

    @property
    def _xmax(self):
        if self.active:
            return self.scr.getmaxyx()[1]
        else:
            return 0

    def _move(self, y, x):
        self.y = y
        self.x = x
        self.scr.mvwin(y, x)

    def background(self, color):
        self._bg = color
        self._on_init()

    def on_click(self, my, mx, click):
        if not self._on_click_warn:
            LOG.warn("{}.on_click() method should be overridden by subclass".format(type(self).__name__))
            self._on_click_warn = True

    def on_init(self):
        if not self._on_init_warn:
            LOG.warn("{}.on_init() method should be overridden by subclass".format(type(self).__name__))
            self._on_init_warn = True

    def on_key(self, getch):
        if not self._on_key_warn:
            LOG.warn("{}.on_key() method should be overridden by subclass".format(type(self).__name__))
            self._on_key_warn = True

    def on_redraw(self):
        if not self._on_redraw_warn:
            LOG.warn("{}.on_redraw() method should be overridden by subclass".format(type(self).__name__))
            self._on_redraw_warn = True

class Desktop(Window):
    """Main curses screen."""

    quit_on_q = True

    def __init__(self, stdscr, fg='white', bg='dgray'):

        LOG.info("Desktop init'ed.")

        super().__init__(stdscr, fg=fg, bg=bg)

        # Desktop parameters
        self._windows = []  # All subwindows
        self._z = Window._z_top

        # Latches
        self._assemble_warn = False

        # Initialize
        self._init_curses()
        self._init_io()
        self._on_init()
        self.scr.refresh()

        # Assemble all subwin's (Any Window subclass inside a Desktop subclass)
        self._assemble()

        #LOG.debug("{}".format(self))

        # Main update
        self._mainloop()

    def __del__(self):

        LOG.info("Desktop del'ed.")

        try:
            getattr(self, 'scr')
        except AttributeError:
            pass
        else:
            if self.scr is not None:
                self.scr.leaveok(0)
                self.scr.scrollok(1)
                self.scr.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()

    def _init_curses(self):
        # Colors
        terminfo = curses.longname()
        # assert '256' in terminfo  # Your env TERM must be xterm-256color!
        assert curses.has_colors()
        curses.start_color()
        curses.use_default_colors()
        ctr = 1
        for fg in CLRS:
            for bg in CLRS:
                if ctr <= curses.COLOR_PAIRS-1 and fg != bg:
                    curses.init_pair(ctr, CLRS[fg], CLRS[bg])
                    PAIRS[(fg,bg)] = curses.color_pair(ctr)
                    ctr += 1

        # I/O
        availmask, _ = curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.meta(1)  # 8b chars
        curses.noecho()  # No auto echo keys to window
        curses.cbreak()  # Don't wait for <Enter>
        curses.curs_set(0)  # Invisible cursor
        curses.delay_output(0)
        curses.mouseinterval(MOUSEINTERVAL)

    def _init_io(self):
        # I/O
        self.scr.leaveok(1)  # Virtual screen cursor after update
        self.scr.scrollok(0)  # Cursor moves off page don't scroll
        self.scr.keypad(1)  # Use special char values

        # User input
        if NONBLOCKING:
            self.scr.nodelay(1)  # Nonblocking getch/str
            self.scr.timeout(NONBLOCKING_TIMEOUT)  # Nonblocking gets, ms
        else:
            self.scr.nodelay(0)
            self.scr.timeout(-1)

    def _assemble(self):
        self.assemble()

    def _draw_shadow(self, window):
        self.scr.hline(window.y+window._ymax, window.x+1, ' ', window.xsize, PAIRS['white', 'black'])
        self.scr.vline(window.y+1, window.x+window._xmax, ' ', window.ysize, PAIRS['white', 'black'])

    def _on_redraw(self):
        self.on_redraw()
        if self.has_border:
            self.scr.border()
        self.scr.noutrefresh()
        for window in self._windows:
            if window.active:
                window._on_redraw()
                if self.has_shadows:
                    self._draw_shadow(window)
                if window.has_border:
                    window.scr.border()
                window.scr.noutrefresh()
            else:
                window.scr = None
        curses.doupdate()

    def move(self, scr, y, x):
        scr._move(y, x)
        self.reinit_all()

    def reinit_all(self): # TODO is this needed?
        self._on_init()
        for each in self._windows:
            each._on_init()
        curses.doupdate()

    def _mainloop(self):
        """Main update loop."""
        loop = True
        while loop:
            # Redraw
            self._on_redraw()
            getch = self.scr.getch()

            # Input
            if getch != -1:
                if getch in (curses.KEY_MOUSE,):
                    _, mx, my, _, click = curses.getmouse()
                    self._on_click(my, mx, click)
                    for window in self._windows:
                        if window.scr is not None and window.scr.enclose(my, mx):
                            window._on_click(my, mx, click)
                elif chr(getch) in 'qQ' and self.quit_on_q:
                    loop = False
                else:
                    self._on_key(getch)

            # Sleep
            if SLEEPTIME:
                curses.napms(int(SLEEPTIME*1000))

    def assemble(self):
        if not self._assemble_warn:
            LOG.warn("{}.assemble() method should be overridden by subclass, searching for subwin's automatically".format(type(self).__name__))
            self._assemble_warn = True

        # Auto assemble and add_win for each Windows subclass defined inside a
        #  Desktop subclass
        for each in [every for every in dir(self) if every[0] != '_']:
            cls = getattr(self, each)
            try:
                if issubclass(cls, Window):
                    self.add_win(cls())
            except TypeError:
                pass

    def add_win(self, window):
        y = min(window.y, self._ymax)
        x = min(window.x, self._xmax)
        ysize = min(window.ysize, self._ymax - window.y)
        xsize = min(window.xsize, self._xmax - window.x)

        if window.active:
            LOG.exception("asdf {} {} {} {}".format(ysize,xsize,y,x))
            subwin = self.scr.subwin(ysize, xsize, y, x)
            if window.scr is not None:
                LOG.error("{}.add_win is overridding window.scr".format(type(window).__name__))
            window.scr = subwin
            window._on_init()
            window.scr.refresh()

            Window._z_top += 1
            window._z = Window._z_top

            LOG.debug("{}".format(window))
            self._windows.append(window)

#TODO From here down is a demo and should be moved!!! ---------vvvvvvvvvv

class GUI(Desktop):
    """Template Desktop subclass."""

    columns = 3

    class MyWin(Window):
        has_border = False
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.t = 0
            self.col = kwargs.get('col', None)
        def on_click(self, my, mx, click):
            self.background('red')
            self.scr.addstr(0, 3, "a")
        def on_init(self):
            self.scr.addstr(0, 0, str(self._z))
        def on_redraw(self):
            self.t += 1
            self.scr.addstr(0, 5, '{}'.format(self.t))

    def assemble(self):
        def gen_screen(ymax, xmax):
            for col in range(self.columns):
                x = col * int(xmax/self.columns)
                for row in range(ymax):
                    yield GUI.MyWin(scr=None,
                                    y=row,
                                    x=x,
                                    ysize=1,
                                    xsize=int(xmax/self.columns),
                                    fg='white',
                                    bg='blue',
                                    col=col)
        for each in gen_screen(*self.scr.getmaxyx()):
            self.add_win(each)

    def on_key(self, getch):
        self.scr.addstr(0, 0, chr(getch))

# Window.has_shadows = True
# Window.has_border = True
class GUI2(Desktop):
    """Template Desktop subclass."""

    t = 0
    class MyWin(Window):
        def on_click(self, my, mx, click):
            self.background('red')
        def on_init(self):
            self.scr.addstr(0, 0, "A")
        def on_redraw(self):
            self.scr.addstr(0, 1, "B")

    def assemble(self):
        self.add_win(GUI2.MyWin())

    def on_redraw(self):
        self.scr.addstr(0, 0, str(datetime.today()))

    def on_click(self, my, mx, click):
        if self.t < 4:
            self.move(self._windows[0], my, mx)
            self.t += 1
        else:
            self._windows = []
            self._on_init()

## FUNCTIONS
#
def run():
    curses.wrapper(GUI)
    # curses.wrapper(GUI2)

if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        sys.stdout.flush()
        sys.stderr.flush()
    except curses.error as err:
        LOG.exception("Curses error caught: {}".format(err))
        if 'add' in str(err):
            LOG.debug("May have written outside of window?")
        raise
    except Exception as err:
        LOG.exception("Error caught: {}".format(err))
        raise

