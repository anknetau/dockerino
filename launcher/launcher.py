#!/usr/bin/env python3
"""
quicklaunch.py — A minimal Quicksilver/Raycast clone for macOS.

Requirements:
    pip install pyobjc

Usage:
    python quicklaunch.py

    Press Option+Space from any app to toggle the launcher.
    Type to search — best match previewed on second line.
    Enter to launch.  ESC to dismiss.

Note: On first run macOS will prompt you to grant Accessibility access
(System Settings → Privacy & Security → Accessibility) so the global
Option+Space hotkey works from other apps.
"""

import os
import subprocess
from pathlib import Path
from Foundation import NSNotificationCenter
from AppKit import NSControlTextDidChangeNotification


import objc
from Foundation import NSObject, NSURL
from AppKit import (
    NSApplication,
    NSApp,
    NSPanel,
    NSView,
    NSTextField,
    NSColor,
    NSFont,
    NSBezierPath,
    NSEvent,
    NSScreen,
    NSWorkspace,
    NSMakeRect,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSApplicationActivationPolicyAccessory,
    NSEventModifierFlagOption,
    NSFloatingWindowLevel,
)

# ── Graceful fallbacks for constants that may differ across PyObjC versions ──
try:
    from AppKit import NSFocusRingTypeNone
except ImportError:
    NSFocusRingTypeNone = 1

try:
    from AppKit import NSWindowCollectionBehaviorStationary
except ImportError:
    NSWindowCollectionBehaviorStationary = 1 << 4   # 16


# ╔══════════════════════════════════════════════════════════════════╗
# ║                     USER CONFIGURATION                          ║
# ╚══════════════════════════════════════════════════════════════════╝

# Each entry is either:
#   "command string"               ← title shown = the command itself
#   ["Friendly Title", "command"]  ← custom title + command
CLI_COMMANDS = [
        ["aaa", "ls -la"],
    # ["Terminal",    "open -a Terminal"],
    # ["iTerm",       "open -a iTerm"],
    # "caffeinate",
    # ["Flush DNS",   "sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder"],
    # ["Copy IP",     "curl -s ifconfig.me | pbcopy"],
    # ["Sleep",       "pmset sleepnow"],
    # ["Lock Screen", "open -a ScreenSaverEngine"],
    # ["Empty Trash", "osascript -e 'tell application \"Finder\" to empty trash'"],
    # ["Wifi Off",    "networksetup -setairportpower en0 off"],
    # ["Wifi On",     "networksetup -setairportpower en0 on"],
]

# Each entry is either:
#   "https://url"                  ← title shown = the URL itself
#   ["Friendly Title", "url"]      ← custom title + URL
URLS = [
    ["GitHub",       "https://github.com"],
    ["Hacker News",  "https://news.ycombinator.com"],
    ["Claude AI",    "https://claude.ai"],
    ["Google",       "https://google.com"],
    ["YouTube",      "https://youtube.com"],
    ["Lobste.rs",    "https://lobste.rs"],
]

INTERNAL_COMMANDS = [
    ["Quit", "QUIT"],
    ["Exit", "QUIT"],
]

# ══════════════════════════════════════════════════════════════════


# ── Layout constants ──────────────────────────────────────────────────────────
WIN_W    = 980   # launcher width  (px)
WIN_H    = 100    # launcher height (px)
CORNER_R = 14    # rounded corner radius

# macOS key codes
KEY_ESC    = 53
KEY_RETURN = 36
KEY_SPACE  = 49

# NSEventMaskKeyDown = 1 << 10
MASK_KEYDOWN = 1 << 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def list_applications():
    """Return (display_name, bundle_path) for every .app macOS can find."""
    dirs = [
        "/Applications",
        "/System/Applications",
        "/System/Applications/Utilities",
        "/System/Library/CoreServices",
        str(Path.home() / "Applications"),
        str(Path.home() / "Applications" / "Setapp"),
    ]
    seen, results = set(), []
    for d in dirs:
        p = Path(d)
        if p.is_dir():
            for app in sorted(p.glob("*.app")):
                if app.name not in seen:
                    seen.add(app.name)
                    results.append((app.stem, str(app)))
    return results


def match_score(query: str, title: str) -> int:
    """
    Score how well *query* matches *title*.
    Returns 0 for no match.  Higher = better.
    """
    q = query.lower()
    t = title.lower()

    if not q:
        return 0
    if q == t:
        return 1000
    if t.startswith(q):
        # longer titles score a bit lower so "Xcode" beats "Xcode Simulator"
        return 900 - len(t)
    if q in t:
        return 700 - len(t)

    # Fuzzy: every character of q must appear in order inside t
    idx = 0
    for ch in q:
        pos = t.find(ch, idx)
        if pos == -1:
            return 0       # no match
        idx = pos + 1
    return 500 - len(t)


# ── Custom views ──────────────────────────────────────────────────────────────

class KeyablePanel(NSPanel):
    @objc.typedSelector(b"B16@0:8")
    def canBecomeKeyWindow(self):
        return True

class BackgroundView(NSView):
    """
    Draws the dark translucent rounded-rect launcher body.
    A thin horizontal rule separates the input row from the preview row.
    """

    def drawRect_(self, rect):
        bounds = self.bounds()

        # ── Main background ────────────────────────────────────────────────
        NSColor.colorWithRed_green_blue_alpha_(0.10, 0.10, 0.12, 0.97).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            bounds, CORNER_R, CORNER_R
        ).fill()

        # ── Separator line ─────────────────────────────────────────────────
        sep_y = WIN_H - 59.0
        sep = NSBezierPath.bezierPath()
        sep.moveToPoint_((CORNER_R + 2, sep_y))
        sep.lineToPoint_((WIN_W - CORNER_R - 2, sep_y))
        NSColor.colorWithWhite_alpha_(0.25, 1.0).setStroke()
        sep.setLineWidth_(0.5)
        sep.stroke()


# ── Application delegate ──────────────────────────────────────────────────────

class AppDelegate(NSObject):

    # Called by Cocoa after the run loop starts
    def applicationDidFinishLaunching_(self, _notification):
        # Run as an agent — no Dock icon, no menu bar
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self._items        = self._build_catalogue()
        self._current_item = None

        self._build_panel()
        self._install_monitors()

    # ── Item catalogue ─────────────────────────────────────────────────────

    def _build_catalogue(self):
        items = []

        # 1. Applications
        for name, path in list_applications():
            items.append({
                "title":   name,
                "type":    "app",
                "target":  path,
                "preview": f"  Launch  ›  {path}",
            })

        # 2. CLI commands
        for entry in CLI_COMMANDS:
            if isinstance(entry, str):
                title = cmd = entry
            else:
                title, cmd = entry
            items.append({
                "title":   title,
                "type":    "cmd",
                "target":  cmd,
                "preview": f"  Run  ›  $ {cmd}",
            })

        # 3. URLs
        for entry in URLS:
            if isinstance(entry, str):
                title = url = entry
            else:
                title, url = entry
            items.append({
                "title":   title,
                "type":    "url",
                "target":  url,
                "preview": f"  Open  ›  {url}",
            })

        # 4. internal commands
        for entry in INTERNAL_COMMANDS:
            if isinstance(entry, str):
                title = icmd = entry
            else:
                title, icmd = entry
            items.append({
                "title":   title,
                "type":    "icmd",
                "target":  icmd,
                "preview": f" {icmd}",
            })


        return items

    # ── Panel construction ─────────────────────────────────────────────────

            
    def _build_panel(self):
        sf  = NSScreen.mainScreen().frame()
        # Position: horizontally centred, ~60 px above vertical centre
        ox  = sf.origin.x + (sf.size.width  - WIN_W) / 2
        oy  = sf.origin.y + (sf.size.height - WIN_H) / 2 + 60

        # panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        panel = KeyablePanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(ox, oy, WIN_W, WIN_H),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        # Float above every normal window, but stay below menu bar / status items
        panel.setLevel_(NSFloatingWindowLevel + 3)
        panel.setOpaque_(False)
        panel.setHasShadow_(True)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorStationary
        )
        panel.setHidesOnDeactivate_(False)
        panel.setMovableByWindowBackground_(True)   # drag anywhere on the body

        # ── Background ─────────────────────────────────────────────────────
        bg = BackgroundView.alloc().initWithFrame_(NSMakeRect(0, 0, WIN_W, WIN_H))
        panel.contentView().addSubview_(bg)

        # Fonts — Menlo is always present on macOS; fallback just in case
        font_input   = (NSFont.fontWithName_size_("Menlo", 22)
                        or NSFont.systemFontOfSize_(22))
        font_preview = (NSFont.fontWithName_size_("Menlo", 12)
                        or NSFont.systemFontOfSize_(12))

        # ── Input text field (top row) ──────────────────────────────────────
        tf = NSTextField.alloc().initWithFrame_(
            NSMakeRect(18, WIN_H - 54, WIN_W - 36, 40)
        )
        tf.setFont_(font_input)
        tf.setTextColor_(NSColor.colorWithWhite_alpha_(0.95, 1.0))
        tf.setBackgroundColor_(NSColor.clearColor())
        tf.setBordered_(False)
        tf.setFocusRingType_(NSFocusRingTypeNone)
        tf.setPlaceholderString_("Search apps, commands, URLs…")


        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self,
            "controlTextDidChange:",
            NSControlTextDidChangeNotification,
            tf
        )


        # tf.setDelegate_(self)
        bg.addSubview_(tf)

        # ── Preview field (bottom row) ──────────────────────────────────────
        pf = NSTextField.alloc().initWithFrame_(
            NSMakeRect(18, 8, WIN_W - 36, 22)
        )
        pf.setFont_(font_preview)
        pf.setTextColor_(NSColor.colorWithWhite_alpha_(0.48, 1.0))
        pf.setBackgroundColor_(NSColor.clearColor())
        pf.setBordered_(False)
        pf.setEditable_(False)
        pf.setSelectable_(False)
        pf.setFocusRingType_(NSFocusRingTypeNone)
        bg.addSubview_(pf)

        self._panel   = panel
        self._input   = tf
        self._preview = pf

    # ── Event monitors ─────────────────────────────────────────────────────

    def _install_monitors(self):
        me = self

        # ---- Global monitor: catches keystrokes from *any* application ----
        # The callback is invoked on the main thread, so UI calls are safe.
        def global_handler(event):
            flags = event.modifierFlags()
            if (flags & NSEventModifierFlagOption) and event.keyCode() == KEY_SPACE:
                me.toggle()

        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            MASK_KEYDOWN, global_handler
        )

        # ---- Local monitor: catches keystrokes inside our own process -----
        def local_handler(event):
            kc    = event.keyCode()
            flags = event.modifierFlags()

            if kc == KEY_ESC:                                    # dismiss
                me.hide()
                return None                                       # swallow

            if kc == KEY_RETURN:                                 # execute
                me.execute()
                return None                                       # swallow

            if (flags & NSEventModifierFlagOption) and kc == KEY_SPACE:
                me.toggle()
                return None

            return event   # pass everything else through

        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            MASK_KEYDOWN, local_handler
        )

    # ── Show / hide / toggle ───────────────────────────────────────────────

    def toggle(self):
        if self._panel.isVisible():
            self.hide()
        else:
            self.show()

    def show(self):
        # Re-centre on the main screen every time it appears
        sf = NSScreen.mainScreen().frame()
        ox = sf.origin.x + (sf.size.width  - WIN_W) / 2
        oy = sf.origin.y + (sf.size.height - WIN_H) / 2 + 60
        self._panel.setFrameOrigin_((ox, oy))

        NSApp.activateIgnoringOtherApps_(True)
        self._panel.makeKeyAndOrderFront_(None)
        self._panel.makeFirstResponder_(self._input)

    def hide(self):
        self._panel.orderOut_(None)
        self._input.setStringValue_("")
        self._preview.setStringValue_("")
        self._current_item = None

    # ── Execute best match ─────────────────────────────────────────────────

    def execute(self):
        query = self._input.stringValue().strip()
        if not query or self._current_item is None:
            return

        item   = self._current_item
        self.hide()

        item_type = item["type"]
        target    = item["target"]

        if item_type == "app":
            # Open the .app bundle by its file URL
            NSWorkspace.sharedWorkspace().openURL_(
                NSURL.fileURLWithPath_(target)
            )
        elif item_type == "url":
            NSWorkspace.sharedWorkspace().openURL_(
                NSURL.URLWithString_(target)
            )
        elif item_type == "cmd":
            # Run in a login shell so PATH / env vars are available
            subprocess.Popen(["bash", "-lc", target])
        elif item_type == "icmd":
            if target == "QUIT":
                NSApp.terminate_(None)

    # ── Fuzzy search ───────────────────────────────────────────────────────

    def _best_match(self, query):
        best_score = 0
        best_item  = None
        for item in self._items:
            s = match_score(query, item["title"])
            if s > best_score:
                best_score = s
                best_item  = item
        return best_item   # None if nothing scored > 0

    # ── NSTextField delegate ───────────────────────────────────────────────

    @objc.typedSelector(b"v@:@")
    def controlTextDidChange_(self, notification):
        query = self._input.stringValue().strip()

        if not query:
            self._current_item = None
            self._preview.setStringValue_("")
            return

        item = self._best_match(query)
        self._current_item = item

        if item:
            self._preview.setStringValue_(item["preview"])
        else:
            self._preview.setStringValue_("  No match found")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app      = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
