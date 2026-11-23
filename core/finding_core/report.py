"""The lines a check prints, counted by kind."""
import os


class Report:
    def __init__(self, root):
        self.root = root
        self.lines = []
        self.counts = {"ERROR": 0, "WARNING": 0, "PENDING": 0}

    def add(self, kind, path, line, msg, step=None):
        where = os.path.relpath(path, self.root) + (":%d" % line if line else "")
        label = kind if step is None else "%s %s" % (kind, step)
        self.lines.append((kind, step, "%-8s %s  %s" % (label, where, msg)))
        self.counts[kind] += 1

    def error(self, path, line, msg):
        self.add("ERROR", path, line, msg)

    def warn(self, path, line, msg):
        self.add("WARNING", path, line, msg)

    def pending(self, step, path, line, msg):
        self.add("PENDING", path, line, msg, step)
