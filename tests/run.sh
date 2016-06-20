#!/bin/sh

# basedir is the root of the test directory in the package
basedir="$(dirname "$0")"
[ "$(echo "$basedir" | cut -c1)" = '/' ] || basedir="$PWD/$basedir"

# rootdir is the root of the package
rootdir="$basedir/.."


die()
{
	echo "$*"
	exit 1
}

# $1=interpreter
# $2=nose
# $3=test_dir
run_nose()
{
	local interpreter="$1"
	local nose="$2"
	local test_dir="$3"

	echo
	echo "==="
	echo "= Running $interpreter $nose..."
	echo "==="
	export PYTHONPATH="$rootdir/tests:$PYTHONPATH"
	cd "$rootdir" || die "Failed to cd to rootdir."
	"$interpreter" "$nose" -v --no-byte-compile "$test_dir" ||\
		die "Test failed"
}

# $1=test_dir
run_testdir()
{
	local test_dir="$1"

	export PYTHONPATH=
	run_nose python2 "$(which nosetests)" "$test_dir"

	export PYTHONPATH=
	run_nose python3 "$(which nosetests3)" "$test_dir"

	local p='import sys; print(":".join(p for p in sys.path if p.startswith("/usr/")))'
	export PYTHONPATH="$(python -c "$p")"
	run_nose pypy "$(which nosetests)" "$test_dir"
}

run_tests()
{
	run_testdir tests
}

run_tests
