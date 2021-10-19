from __future__ import division, absolute_import, print_function, unicode_literals

__all__ = [
	"VERSION_MAJOR",
	"VERSION_MINOR",
	"VERSION_EXTRA",
	"VERSION_STRING",
]

VERSION_MAJOR	= 1
VERSION_MINOR	= 11
VERSION_EXTRA	= ""

VERSION_STRING = "%d.%d%s" % (VERSION_MAJOR, VERSION_MINOR, VERSION_EXTRA)
