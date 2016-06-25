#!/bin/sh

die()
{
	echo "$*" >&2
	exit 1
}

usage()
{
	echo "Usage: run-linuxcnc-demo.sh [/path/to/linuxcnc]"
	echo
	echo " /path/to/linuxcnc: Path to 'linuxcnc' start script"
}

if [ $# -ge 1 ] && [ "$1" = "-h" -o "$1" = "--help" ]; then
	usage
	exit 0
fi
if [ $# -eq 0 ]; then
	linuxcnc="linuxcnc"
elif [ $# -eq 1 ]; then
	linuxcnc="$1"
else
	usage
	exit 1
fi


# basedir = directory where this script lives in
basedir="$(dirname "$0")"
[ "$(echo "$basedir" | cut -c1)" = '/' ] || basedir="$PWD/$basedir"

# rootdir = root of the pyprofibus repository
rootdir="$basedir/.."

[ -x "$rootdir/pyprofibus-linuxcnc-hal" ] || die "pyprofibus-linuxcnc-hal not found"

cleanup()
{
	rm -f "/tmp/linuxcnc-demo.ngc"
}

cleanup
trap cleanup EXIT
cp "$basedir/linuxcnc-demo.ngc" /tmp/ || die "Failed to copy linuxcnc-demo.ngc"

# Start LinuxCNC
(
	cd "$basedir" || die "Failed to 'cd $basedir'"
	PATH="$rootdir/:$PATH"\
	PYTHONPATH="$rootdir/:$PYTHONPATH"\
		"$linuxcnc" "$basedir/linuxcnc-demo.ini" ||\
		die "LinuxCNC exited with an error"
)
