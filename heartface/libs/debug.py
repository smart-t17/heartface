#!/usr/bin/env python
# coding=utf-8

import sys

def _start_debugger(type, value, traceback):
    import ipdb;
    ipdb.post_mortem(traceback)

sys.excepthook = _start_debugger
