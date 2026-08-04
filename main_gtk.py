#!/usr/bin/env python3
"""Legacy GTK4 entry point kept during the Qt migration."""

import sys

from lume.app import LumeApplication


if __name__ == "__main__":
    raise SystemExit(LumeApplication().run(sys.argv))
