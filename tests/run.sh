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

# $1=executable_name
find_executable()
{
	local executable_name="$1"

	local executable_path="$(which "$executable_name")"
	[ -n "$executable_path" ] ||\
		die "$executable_name executable not found."\
		    "Please install $executable_name."
	RET="$executable_path"
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

	find_executable nosetests
	local nosetests="$RET"
	find_executable nosetests3
	local nosetests3="$RET"

	export PYTHONPATH=
	run_nose python2 "$nosetests" "$test_dir"

	export PYTHONPATH=
	run_nose python3 "$nosetests3" "$test_dir"

	local p='import sys; print(":".join(p for p in sys.path if p.startswith("/usr/")))'
	export PYTHONPATH="$(pypy -c "$p"):$(python2 -c "$p")"
	run_nose pypy "$nosetests" "$test_dir"
}

run_tests()
{
	run_testdir tests
}

run_tests
