#!/bin/sh

# basedir is the root of the test directory in the package
basedir="$(dirname "$0")"
[ "$(echo "$basedir" | cut -c1)" = '/' ] || basedir="$PWD/$basedir"

# rootdir is the root of the package
rootdir="$basedir/.."


die()
{
	[ -n "$*" ] && echo "$*" >&2
	exit 1
}

# $1=interpreter
# $2=test_dir
run_pyunit()
{
	local interpreter="$1"
	local test_dir="$2"

	(
		echo
		echo "==="
		echo "= Running $interpreter..."
		echo "==="
		export PYTHONPATH="$rootdir/tests:$PYTHONPATH"
		cd "$rootdir" || die "Failed to cd to rootdir."
		"$interpreter" -m unittest --failfast --buffer --catch "$test_dir" ||\
			die "Test failed"
	) || die
}

test_interpreter()
{
	"$1" -c 'import serial' >/dev/null 2>&1
}

# $1=test_dir
run_testdir()
{
	local test_dir="$1"

	unset PYTHONPATH
	unset PYTHONSTARTUP
	unset PYTHONY2K
	unset PYTHONOPTIMIZE
	unset PYTHONDEBUG
	export PYTHONDONTWRITEBYTECODE=1
	unset PYTHONINSPECT
	unset PYTHONIOENCODING
	unset PYTHONNOUSERSITE
	unset PYTHONUNBUFFERED
	unset PYTHONVERBOSE
	export PYTHONWARNINGS=once
	export PYTHONHASHSEED=random

	local exec_any=0
	if test_interpreter python2; then
		run_pyunit python2 "$test_dir"
		local exec_any=1
	fi
	if test_interpreter python3; then
		run_pyunit python3 "$test_dir"
		local exec_any=1
	fi
	if test_interpreter pypy3; then
		run_pyunit pypy3 "$test_dir"
		local exec_any=1
	fi
	if [ $exec_any -eq 0 ]; then
		die "Failed to find any usable Python interpreter."
	fi
}

run_tests()
{
	run_testdir tests
}

run_tests
