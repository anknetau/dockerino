#!/usr/bin/env python3
"""
launcher.py — A minimal Quicksilver/Raycast clone for macOS.

Requirements:
    pip install pyobjc

Usage:
    python launcher.py

Press Option+Space from any app to toggle the launcher.
Type to search — matched items shown in scrollable list.
Use ↑/↓ to navigate, Enter to launch, ESC to dismiss.
"""

import subprocess
from pathlib import Path
import signal
import sys
import objc
from Foundation import NSObject, NSNotificationCenter, NSURL, NSIndexSet
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
    NSScrollView,
    NSTableView,
    NSTableColumn,
    NSControlTextDidChangeNotification,
)

try:
    from AppKit import NSFocusRingTypeNone
except ImportError:
    NSFocusRingTypeNone = 1

try:
    from AppKit import NSWindowCollectionBehaviorStationary
except ImportError:
    NSWindowCollectionBehaviorStationary = 1 << 4

# ────────── CONFIG ──────────
CLI_COMMANDS = [
    ["aaa", "ls -la"],
]

URLS = [
    ["GitHub", "https://github.com"],
    ["Hacker News", "https://news.ycombinator.com"],
    ["Claude AI", "https://claude.ai"],
    ["Google", "https://google.com"],
    ["YouTube", "https://youtube.com"],
    ["Lobste.rs", "https://lobste.rs"],
]

INTERNAL_COMMANDS = [
    ["Quit", "QUIT"],
    ["Exit", "QUIT"],
]

WIN_W = 980
WIN_H = 500
CORNER_R = 14
LIST_ITEM_HEIGHT = 28

KEY_ESC = 53
KEY_RETURN = 36
KEY_SPACE = 49
KEY_UP = 126
KEY_DOWN = 125
MASK_KEYDOWN = 1 << 10

# Layout constants
INPUT_H = 40
INPUT_Y = WIN_H - 54        # 446
SEP_Y   = WIN_H - 59        # 441  (drawn by BackgroundView)
PREVIEW_Y = 8
PREVIEW_H = 22
LIST_BOTTOM = PREVIEW_Y + PREVIEW_H + 6   # 36
LIST_HEIGHT = SEP_Y - LIST_BOTTOM         # 405


# ────────── Helpers ──────────
def list_applications():
    dirs = [
        "/Applications",
        "/System/Applications",
        "/System/Applications/Utilities",
        "/System/Library/CoreServices",
        str(Path.home() / "Applications"),
        str(Path.home() / "Applications/Setapp"),
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
    q, t = query.lower(), title.lower()
    if not q:
        return 0
    if q == t:
        return 1000
    if t.startswith(q):
        return 900 - len(t)
    if q in t:
        return 700 - len(t)
    idx = 0
    for ch in q:
        pos = t.find(ch, idx)
        if pos == -1:
            return 0
        idx = pos + 1
    return 500 - len(t)


# ────────── Views ──────────
class KeyablePanel(NSPanel):
    @objc.typedSelector(b"B16@0:8")
    def canBecomeKeyWindow(self):
        return True


class BackgroundView(NSView):
    def drawRect_(self, rect):
        bounds = self.bounds()
        NSColor.colorWithRed_green_blue_alpha_(0.10, 0.10, 0.12, 0.97).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bounds, CORNER_R, CORNER_R).fill()
        sep_y = WIN_H - 59.0
        sep = NSBezierPath.bezierPath()
        sep.moveToPoint_((CORNER_R + 2, sep_y))
        sep.lineToPoint_((WIN_W - CORNER_R - 2, sep_y))
        NSColor.colorWithWhite_alpha_(0.25, 1.0).setStroke()
        sep.setLineWidth_(0.5)
        sep.stroke()


# ────────── AppDelegate ──────────
class AppDelegate(NSObject):

    def applicationDidFinishLaunching_(self, _notification):
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        self._items = self._build_catalogue()
        self._matches = []
        self._selection_idx = -1
        self._current_item = None
        self._build_panel()
        self._install_monitors()

    # ── Catalogue ──

    def _build_catalogue(self):
        items = []
        for name, path in list_applications():
            items.append({"title": name, "type": "app", "target": path,
                          "preview": f"  Launch  ›  {path}"})
        for entry in CLI_COMMANDS:
            title, cmd = (entry, entry) if isinstance(entry, str) else entry
            items.append({"title": title, "type": "cmd", "target": cmd,
                          "preview": f"  Run  ›  $ {cmd}"})
        for entry in URLS:
            title, url = (entry, entry) if isinstance(entry, str) else entry
            items.append({"title": title, "type": "url", "target": url,
                          "preview": f"  Open  ›  {url}"})
        for entry in INTERNAL_COMMANDS:
            title, icmd = (entry, entry) if isinstance(entry, str) else entry
            items.append({"title": title, "type": "icmd", "target": icmd,
                          "preview": f" {icmd}"})
        return items

    # ── Panel ──

    def _build_panel(self):
        sf = NSScreen.mainScreen().frame()
        ox = sf.origin.x + (sf.size.width - WIN_W) / 2
        oy = sf.origin.y + (sf.size.height - WIN_H) / 2 + 60

        panel = KeyablePanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(ox, oy, WIN_W, WIN_H),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        panel.setFloatingPanel_(True)
        panel.setLevel_(NSFloatingWindowLevel + 3)
        panel.setOpaque_(False)
        panel.setHasShadow_(True)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary
        )
        panel.setHidesOnDeactivate_(False)
        panel.setMovableByWindowBackground_(True)

        bg = BackgroundView.alloc().initWithFrame_(NSMakeRect(0, 0, WIN_W, WIN_H))
        panel.contentView().addSubview_(bg)
        bg.setNeedsDisplay_(True)

        font_input   = NSFont.fontWithName_size_("Menlo", 22) or NSFont.systemFontOfSize_(22)
        font_list    = NSFont.fontWithName_size_("Menlo", 13) or NSFont.systemFontOfSize_(13)
        font_preview = NSFont.fontWithName_size_("Menlo", 12) or NSFont.systemFontOfSize_(12)

        # ── Input field ──
        tf = NSTextField.alloc().initWithFrame_(
            NSMakeRect(18, INPUT_Y, WIN_W - 36, INPUT_H)
        )
        tf.setFont_(font_input)
        tf.setTextColor_(NSColor.colorWithWhite_alpha_(0.95, 1.0))
        tf.setBackgroundColor_(NSColor.clearColor())
        tf.setBordered_(False)
        tf.setFocusRingType_(NSFocusRingTypeNone)
        tf.setPlaceholderString_("Search apps, commands, URLs…")
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "controlTextDidChange_", NSControlTextDidChangeNotification, tf
        )
        bg.addSubview_(tf)

        # ── Scrollable results list ──
        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, LIST_BOTTOM, WIN_W, LIST_HEIGHT)
        )
        scroll.setDrawsBackground_(False)
        scroll.setHasVerticalScroller_(True)
        scroll.setHasHorizontalScroller_(False)
        scroll.setAutohidesScrollers_(True)
        scroll.setVerticalScrollElasticity_(1)   # NSScrollElasticityNone

        tv = NSTableView.alloc().initWithFrame_(
            NSMakeRect(0, 0, WIN_W, LIST_HEIGHT)
        )
        col = NSTableColumn.alloc().initWithIdentifier_("title")
        col.setWidth_(WIN_W - 4)
        col.setResizingMask_(0)   # NSTableColumnNoResizing
        col.dataCell().setFont_(font_list)
        col.dataCell().setTextColor_(NSColor.colorWithWhite_alpha_(0.78, 1.0))
        tv.addTableColumn_(col)
        tv.setHeaderView_(None)
        tv.setBackgroundColor_(NSColor.clearColor())
        tv.setRowHeight_(LIST_ITEM_HEIGHT)
        tv.setIntercellSpacing_((0, 2))
        tv.setGridStyleMask_(0)
        tv.setFocusRingType_(NSFocusRingTypeNone)
        tv.setAllowsEmptySelection_(True)
        # Suppress the native blue selection bar so we draw our own highlight
        tv.setSelectionHighlightStyle_(-1)   # NSTableViewSelectionHighlightStyleNone
        tv.setDataSource_(self)
        tv.setDelegate_(self)

        scroll.setDocumentView_(tv)
        bg.addSubview_(scroll)

        # ── Preview field ──
        pf = NSTextField.alloc().initWithFrame_(
            NSMakeRect(18, PREVIEW_Y, WIN_W - 36, PREVIEW_H)
        )
        pf.setFont_(font_preview)
        pf.setTextColor_(NSColor.colorWithWhite_alpha_(0.48, 1.0))
        pf.setBackgroundColor_(NSColor.clearColor())
        pf.setBordered_(False)
        pf.setEditable_(False)
        pf.setSelectable_(False)
        pf.setFocusRingType_(NSFocusRingTypeNone)
        bg.addSubview_(pf)

        self._panel  = panel
        self._input  = tf
        self._table  = tv
        self._preview = pf

    # ── NSTableViewDataSource ──

    def numberOfRowsInTableView_(self, tv):
        return len(self._matches)

    def tableView_objectValueForTableColumn_row_(self, tv, col, row):
        if 0 <= row < len(self._matches):
            return self._matches[row]["title"]
        return ""

    # ── NSTableViewDelegate ──

    def tableView_willDisplayCell_forTableColumn_row_(self, tv, cell, col, row):
        """Draw our own selection highlight instead of the native blue bar."""
        if row == self._selection_idx:
            cell.setTextColor_(NSColor.whiteColor())
            cell.setBackgroundColor_(
                NSColor.colorWithRed_green_blue_alpha_(0.18, 0.44, 0.95, 0.40)
            )
            cell.setDrawsBackground_(True)
        else:
            cell.setTextColor_(NSColor.colorWithWhite_alpha_(0.78, 1.0))
            cell.setDrawsBackground_(False)

    # ── Visibility ──

    def toggle(self):
        if self._panel.isVisible():
            self.hide()
        else:
            self.show()

    def show(self):
        sf = NSScreen.mainScreen().frame()
        ox = sf.origin.x + (sf.size.width - WIN_W) / 2
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
        self._matches = []
        self._selection_idx = -1
        self._table.reloadData()

    def execute(self):
        if self._current_item is None:
            return
        item = self._current_item
        self.hide()
        if item["type"] == "app":
            NSWorkspace.sharedWorkspace().openURL_(NSURL.fileURLWithPath_(item["target"]))
        elif item["type"] == "url":
            NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(item["target"]))
        elif item["type"] == "cmd":
            subprocess.Popen(["bash", "-lc", item["target"]])
        elif item["type"] == "icmd" and item["target"] == "QUIT":
            NSApp.terminate_(None)

    # ── Search logic ──

    def _update_matches(self, query):
        scored = [
            (item, match_score(query, item["title"])) for item in self._items
        ]
        self._matches = sorted(
            [i for i, s in scored if s > 0],
            key=lambda x: -match_score(query, x["title"]),
        )
        self._selection_idx = 0 if self._matches else -1
        self._current_item = (
            self._matches[self._selection_idx] if self._selection_idx >= 0 else None
        )
        self._table.reloadData()
        if self._selection_idx >= 0:
            self._table.scrollRowToVisible_(self._selection_idx)
        self._preview.setStringValue_(
            self._current_item["preview"] if self._current_item
            else ("  No match found" if query else "")
        )

    def _move_selection(self, delta):
        """Move highlight up/down without re-running the search query."""
        if not self._matches:
            return
        self._selection_idx = max(
            0, min(len(self._matches) - 1, self._selection_idx + delta)
        )
        self._current_item = self._matches[self._selection_idx]
        # Redraw rows so tableView_willDisplayCell fires with new selection_idx
        self._table.reloadData()
        self._table.scrollRowToVisible_(self._selection_idx)
        self._preview.setStringValue_(self._current_item["preview"])

    # ── Event monitors ──

    def _install_monitors(self):
        me = self

        def global_handler(event):
            if (event.modifierFlags() & NSEventModifierFlagOption) and \
               event.keyCode() == KEY_SPACE:
                me.toggle()

        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            MASK_KEYDOWN, global_handler
        )

        def local_handler(event):
            kc = event.keyCode()
            if kc == KEY_ESC:
                me.hide()
                return None
            if kc == KEY_RETURN:
                me.execute()
                return None
            if kc == KEY_UP:
                me._move_selection(-1)
                return None
            if kc == KEY_DOWN:
                me._move_selection(1)
                return None
            if (event.modifierFlags() & NSEventModifierFlagOption) and \
               kc == KEY_SPACE:
                me.toggle()
                return None
            return event

        NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            MASK_KEYDOWN, local_handler
        )

    @objc.typedSelector(b"v@:@")
    def controlTextDidChange_(self, notification):
        query = self._input.stringValue().strip()
        self._update_matches(query)


def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    NSApp.terminate_(None)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()

