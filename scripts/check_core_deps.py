#!/usr/bin/env python
# -*- coding: utf-8 -*-

import importlib.util
import sys


def main():
    modules = sys.argv[1:]
    if not modules:
        print("No modules provided.")
        return 1

    missing = [m for m in modules if importlib.util.find_spec(m) is None]
    if missing:
        print("Missing modules: " + ", ".join(missing))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
