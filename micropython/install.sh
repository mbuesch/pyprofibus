#!/bin/sh
#
# Build pyprofibus and install on a Micropython board.
#

basedir="$(dirname "$0")"
[ "$(echo "$basedir" | cut -c1)" = '/' ] || basedir="$PWD/$basedir"

rootdir="$(realpath -m "$basedir/..")"

die()
{
	echo "ERROR: $*" >&2
	exit 1
}

echos()
{
	printf '%s' "$*"
}

build()
{
	echo "=== build ==="

	cd "$rootdir" || die "Failed to switch to root dir."

	local gsds="$(find . -maxdepth 1 -name '*.gsd') $(find misc/ -maxdepth 1 -name '*.gsd')"
	local pys="$(find pyprofibus/ -name '*.py') $(find stublibs/ -name '*.py') $(find examples -maxdepth 1 -name 'example_*.py')"
	local confs="$(find examples -maxdepth 1 -name '*.conf')"

	local gsdparser_opts="--dump-strip --dump-notext --dump-noextuserprmdata \
		--dump-module '6ES7 138-4CA01-0AA0 PM-E DC24V' \
		--dump-module '6ES7 132-4BB30-0AA0  2DO DC24V' \
		--dump-module '6ES7 132-4BB30-0AA0  2DO DC24V' \
		--dump-module '6ES7 131-4BD01-0AA0  4DI DC24V' \
		--dump-module 'Master_O Slave_I  1 by unit' \
		--dump-module 'Master_I Slave_O  1 by unit' \
		--dump-module 'dummy output module' \
		--dump-module 'dummy input module' \
		$modules"

	local targets=
	[ -n "$clean" ] && local targets="$targets clean"
	local targets="$targets all"
	for target in $targets; do
		echo "--- $target ---"
		make -j "$(getconf _NPROCESSORS_ONLN)" -f "$rootdir/micropython/Makefile" \
			SRCDIR="." \
			MAINPYDIR="./micropython" \
			BUILDDIR="$builddir" \
			MPYCROSS="$mpycross" \
			MARCH="$march" \
			GSDPARSER_OPTS="$gsdparser_opts" \
			PYS="$pys" \
			GSDS="$gsds" \
			CONFS="$confs" \
			$target || die "make failed."
	done
}

pyboard()
{
	echo "$pyboard -d $dev $*"
	"$pyboard" -d "$dev" "$@" || die "pyboard: $pyboard failed."
}

reboot_dev()
{
	pyboard --no-follow -c 'import machine as m;m.reset()'
}

format_flash()
{
	local wd_timeout="5000"

	local cmd="import machine as m, flashbdev as f, uos as u;"
	cmd="${cmd}m.WDT(0,${wd_timeout}).feed();"
	cmd="${cmd}u.umount('/');"
	cmd="${cmd}u.VfsLfs2.mkfs(f.bdev);"
	cmd="${cmd}u.mount(u.VfsLfs2(f.bdev), '/');"
	pyboard -c "$cmd"
}

transfer()
{
	local from="$1"
	local to="$2"

	if [ -d "$from" ]; then
		pyboard -f mkdir "$to"
		for f in "$from"/*; do
			transfer "$f" "$to/$(basename "$f")"
		done
		return
	fi
	pyboard -f cp "$from" "$to"
}

transfer_to_device()
{
	echo "=== transfer to device $dev ==="

	format_flash
	reboot_dev
	sleep 2
	for f in "$builddir"/*; do
		transfer "$f" :/"$(basename $f)"
	done
	reboot_dev
}

builddir="$rootdir/build/micropython"
buildonly=0
dev="/dev/ttyUSB0"
march="xtensawin"
pyboard="pyboard.py"
mpycross="mpy-cross"
modules=
clean=

while [ $# -ge 1 ]; do
	[ "$(echos "$1" | cut -c1)" != "-" ] && break

	case "$1" in
	-h|--help)
		echo "install.sh [OPTIONS] [TARGET-UART-DEVICE]"
		echo
		echo "Build pyprofibus and install on a Micropython board."
		echo
		echo "TARGET-UART-DEVICE:"
		echo " Target serial device. Default: /dev/ttyUSB0"
		echo
		echo "Options:"
		echo " -c|--clean          Clean before build."
		echo " -b|--build-only     Build only. Do not install."
		echo " -B|--build-dir DIR  Set the build directory."
		echo "                     Default: build/micropython"
		echo " -a|--march ARCH     Target architecture for cross compile."
		echo "                     Default: xtensawin"
		echo " -m|--module NAME    Include GSD module NAME."
		echo "                     Can be specified multiple times for multiple modules."
		echo "                     Enter your 'module_X' names from your configuration here."
		echo " -M|--mpycross PATH  Path to mpy-cross executable."
		echo "                     Default: mpy-cross"
		echo " -p|--pyboard PATH   Path to pyboard executable."
		echo "                     Default: pyboard.py"
		echo " -h|--help           Show this help."
		exit 0
		;;
	-b|--build-only)
		buildonly=1
		;;
	-B|--build-dir)
		shift
		builddir="$1"
		;;
	-a|--march)
		shift
		march="$1"
		;;
	-p|--pyboard)
		shift
		pyboard="$1"
		;;
	-M|--mpycross)
		shift
		mpycross="$1"
		;;
	-m|--module)
		shift
		modules="$modules --dump-module '$1'"
		;;
	-c|--clean)
		clean=1
		;;
	*)
		die "Unknown option: $1"
		;;
	esac
	shift
done
if [ $# -ge 1 ]; then
	dev="$1"
	shift
fi
if [ $# -ge 1 ]; then
	die "Too many arguments."
fi

build
[ $buildonly -eq 0 ] && transfer_to_device
exit 0
