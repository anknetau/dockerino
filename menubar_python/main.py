#!/usr/bin/env python3
"""
Entry point: instantiates the Cocoa application and wires up the delegate.
"""

from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from PyObjCTools import AppHelper

from delegate import AppDelegate


def main() -> None:
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
