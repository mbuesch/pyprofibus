#!/bin/sh
#
# Generate documentation
#


basedir="$(dirname "$0")"
[ "$(echo "$basedir" | cut -c1)" = '/' ] || basedir="$PWD/$basedir"

srcdir="$basedir/.."


die()
{
	echo "$*" >&2
	exit 1
}

gen()
{
	local rst="$1"
	local docname="$(basename "$rst" .rst)"
	local dir="$(dirname "$rst")"
	local html="$dir/$docname.html"

	echo "Generating $(realpath --relative-to="$srcdir" "$html") from $(realpath --relative-to="$srcdir" "$rst") ..."

	python3 -m readme_renderer -o "$html" "$rst" ||\
		die "Failed to generate"
}

for i in $(find "$srcdir" \( -name submodules -prune \) -o \( -name toolchain-build -prune \) -o \( -name crcgen -prune \) -o \( -name '*.rst' -print \)); do
	gen "$i"
done

exit 0
