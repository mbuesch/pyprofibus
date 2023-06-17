#!/bin/sh

srcdir="$(dirname "$0")"
[ "$(echo "$srcdir" | cut -c1)" = '/' ] || srcdir="$PWD/$srcdir"

srcdir="$srcdir/.."

die() { echo "$*"; exit 1; }

# Import the makerelease.lib
# http://bues.ch/gitweb?p=misc.git;a=blob_plain;f=makerelease.lib;hb=HEAD
for path in $(echo "$PATH" | tr ':' ' '); do
	[ -f "$MAKERELEASE_LIB" ] && break
	MAKERELEASE_LIB="$path/makerelease.lib"
done
[ -f "$MAKERELEASE_LIB" ] && . "$MAKERELEASE_LIB" || die "makerelease.lib not found."

hook_get_version()
{
	local file="$1/pyprofibus/version.py"
	local maj="$(cat "$file" | grep -Ee'^VERSION_MAJOR\s+=\s+' | head -n1 | awk '{print $3;}')"
	local min="$(cat "$file" | grep -Ee '^VERSION_MINOR\s+=\s+' | head -n1 | awk '{print $3;}')"
	local ext="$(cat "$file" | grep -Ee '^VERSION_EXTRA\s+=\s+' | head -n1 | awk '{print $3;}' | cut -d'"' -f2)"
	version="${maj}.${min}${ext}"
}

hook_post_checkout()
{
	info "Pulling in git submodules"
	git submodule update --init --recursive

	default_hook_post_checkout "$@"

	rm -r "$1"/maintenance
}

hook_testbuild()
{
	default_hook_testbuild "$@"

	if which mpy-cross >/dev/null 2>&1; then
		# Try a Micropython test build.
		sh "$1/micropython/install.sh" --clean --build-only
	else
		warn "mpy-cross not available. Skipping Micropython test."
	fi
}

hook_regression_tests()
{
	default_hook_regression_tests "$@"

	# Run selftests
	sh "$1/tests/run.sh"
}

do_build()
{
	local target="$1"
	local checkout_dir="$2"

	local builddir="$checkout_dir/phy_fpga"
	local bindir="$builddir/bin/$target"

	make -C "$builddir" TARGET="$target"

	mkdir -p "$bindir"
	for ftype in .bin .asc .blif .rpt .json _yosys.log _nextpnr.log; do
		local binfile="${target}_pyprofibusphy${ftype}"
		cp "$builddir/$binfile" "$bindir/$binfile"
	done
	mv "$builddir/${target}_program.sh" "$bindir/${target}_program.sh"

	make -C "$builddir" TARGET="$target" clean
}

hook_pre_archives()
{
	local archive_dir="$1"
	local checkout_dir="$2"

	do_build tinyfpga_bx "$checkout_dir"
}

hook_doc_archives()
{
	local archive_dir="$1"
	local checkout_dir="$2"

	local doc_name="$project-doc-$version"
	local doc_dir="$tmpdir/$doc_name"
	mkdir "$doc_dir" ||\
		die "Failed to create directory '$doc_dir'"
	(
		cd "$checkout_dir" || die "Failed to cd '$checkout_dir'"
		rsync --recursive --prune-empty-dirs \
			--include='/doc/' \
			--include='/doc/**/' \
			--include='/doc/**.pdf' \
			--include='/doc/**.png' \
			--include='/doc/**.jpg' \
			--include='/doc/**.jpeg' \
			--include='/doc/**.1' \
			--include='/doc/**.html' \
			--include='/doc/**.txt' \
			--include='/doc/**.ods' \
			--include='/doc/**/README' \
			--include='/micropython/' \
			--include='/micropython/**/' \
			--include='/micropython/**.html' \
			--include='/*.html' \
			--include='/*.txt' \
			--exclude='*' \
			. "$doc_dir" ||\
			die "Failed to copy documentation."
		cd "$tmpdir" || die "Failed to cd '$tmpdir'"
		tar --owner=root --group=root -c -J -f "$archive_dir"/$doc_name.tar.xz \
			"$doc_name" ||\
			die "Failed to create doc archive."
	) || die
}

project=pyprofibus
default_archives=py-sdist-xz
makerelease "$@"
