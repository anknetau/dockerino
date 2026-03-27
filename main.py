#!/usr/bin/env python3
from Foundation import NSURL
from AppKit import NSWorkspace

def main():
    url = NSURL.URLWithString_("https://www.apple.com")
    if url is None:
        raise ValueError("Invalid URL")

    ok = NSWorkspace.sharedWorkspace().openURL_(url)
    print(f"opened: {ok}")

if __name__ == "__main__":
    main()
