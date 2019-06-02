#!/bin/sh
#
# FPGA toolchain install script.
# This script installs the full FPGA toolchain into the
# directory specified as INSTALLDIR.
#


# The toolchain will be installed into this directory:
INSTALLDIR="$HOME/fpga-toolchain"

# The following directory will be used as temporary build directory:
BUILDDIR="./toolchain-build"

# Run at most this many build processes in parallel:
PARALLEL="$(getconf _NPROCESSORS_ONLN)"

# The following tools are needed to build the toolchain:
# - gcc
# - clang
# - python3
# - cmake
# - git
#
# Please ensure that all these tools are installed in the system.



#####################################################################
#####################################################################
#####################################################################


# Source repositories:
REPO_ICESTORM="https://github.com/cliffordwolf/icestorm.git"
REPO_NEXTPNR="https://github.com/YosysHQ/nextpnr.git"
REPO_YOSYS="https://github.com/YosysHQ/yosys.git"
REPO_TINYPROG="https://github.com/tinyfpga/TinyFPGA-Bootloader.git"

BUILD_ICESTORM=1
BUILD_NEXTPNR=1
BUILD_YOSYS=1
BUILD_TINYPROG=1

die()
{
	echo "$*" >&2
	exit 1
}

checkprog()
{
	local prog="$1"
	which "$prog" >/dev/null ||\
		die "$prog is not installed. Please install it by use of the distribution package manager (apt, apt-get, rpm, etc...)"
}

[ "$(id -u)" = "0" ] && die "Do not run this as root!"
checkprog gcc
checkprog clang
checkprog python3
checkprog cmake
checkprog git

BUILDDIR="$(realpath -m -s "$BUILDDIR")"
INSTALLDIR="$(realpath -m -s "$INSTALLDIR")"
echo "BUILDDIR=$BUILDDIR"
echo "INSTALLDIR=$INSTALLDIR"
echo "PARALLEL=$PARALLEL"
[ -n "$BUILDDIR" -a -n "$INSTALLDIR" ] || die "Failed to resolve directories"
echo


# Cleanup
rm -rf "$BUILDDIR" || die "Failed to cleanup BUILDDIR"
mkdir -p "$BUILDDIR" || die "Failed to create BUILDDIR"
mkdir -p "$INSTALLDIR" || die "Failed to create INSTALLDIR"

newpath="\$PATH"


# Project Icestorm
if [ $BUILD_ICESTORM -ne 0 ]; then
	echo "Building icestorm..."
	cd "$BUILDDIR" || die "Failed to cd to builddir."
	git clone "$REPO_ICESTORM" "$BUILDDIR/icestorm" || die "Failed to clone icestorm"
	cd "$BUILDDIR/icestorm" || die "Failed to cd to icestorm."
	export PREFIX="$INSTALLDIR/icestorm"
	make -j "$PARALLEL" PREFIX="$PREFIX" || die "Failed to build icestorm"
	rm -rf "$PREFIX" || die "Failed to clean install icestorm"
	make install PREFIX="$PREFIX" || die "Failed to install icestorm"
	newpath="$PREFIX/bin:$newpath"
fi


# nextpnr
if [ $BUILD_NEXTPNR -ne 0 ]; then
	echo "Building nextpnr..."
	cd "$BUILDDIR" || die "Failed to cd to builddir."
	git clone "$REPO_NEXTPNR" "$BUILDDIR/nextpnr" || die "Failed to clone nextpnr"
	mkdir "$BUILDDIR/nextpnr/builddir" || die "Failed to create nextpnr builddir"
	cd "$BUILDDIR/nextpnr/builddir" || die "Failed to cd to nextpnr."
	export PREFIX="$INSTALLDIR/nextpnr"
	cmake -DARCH=ice40 -DICEBOX_ROOT="$INSTALLDIR/icestorm/share/icebox" -DCMAKE_INSTALL_PREFIX="$PREFIX" .. || die "Failed to build nextpnr"
	make -j "$PARALLEL" || die "Failed to build nextpnr"
	rm -rf "$PREFIX" || die "Failed to clean install nextpnr"
	make install || die "Failed to install nextpnr"
	newpath="$PREFIX/bin:$newpath"
fi


# yosys
if [ $BUILD_YOSYS -ne 0 ]; then
	echo "Building yosys..."
	cd "$BUILDDIR" || die "Failed to cd to builddir."
	git clone "$REPO_YOSYS" "$BUILDDIR/yosys" || die "Failed to clone yosys"
	cd "$BUILDDIR/yosys" || die "Failed to cd to yosys."
	export PREFIX="$INSTALLDIR/yosys"
	make config-clang PREFIX="$PREFIX" || die "Failed to configure yosys"
	make -j "$PARALLEL" PREFIX="$PREFIX" || die "Failed to build yosys"
	rm -rf "$PREFIX" || die "Failed to clean install yosys"
	make install PREFIX="$PREFIX" || die "Failed to install yosys"
	newpath="$PREFIX/bin:$newpath"
fi


# tinyprog
if [ $BUILD_TINYPROG -ne 0 ]; then
	echo "Building tinyprog..."
	cd "$BUILDDIR" || die "Failed to cd to builddir."
	git clone "$REPO_TINYPROG" "$BUILDDIR/TinyFPGA-Bootloader" || die "Failed to clone tinyprog"
	cd "$BUILDDIR/TinyFPGA-Bootloader/programmer" || die "Failed to cd to tinyprog."
	export PREFIX="$INSTALLDIR/tinyprog"
	rm -rf "$PREFIX" || die "Failed to clean install tinyprog"
	mkdir -p "$PREFIX/lib" || die "Failed to create tinyprog lib"
	mkdir -p "$PREFIX/bin" || die "Failed to create tinyprog bin"
	cp -r "$BUILDDIR/TinyFPGA-Bootloader/programmer/tinyprog" "$PREFIX/lib/" || die "Failed to install tinyprog"
	cat > "$PREFIX/bin/tinyprog" <<EOF
#!/bin/sh
export PYTHONPATH="$PREFIX/lib/:\$PYTHONPATH"
exec python3 "$PREFIX/lib/tinyprog" "\$@"
EOF
	[ -f "$PREFIX/bin/tinyprog" ] || die "Failed to install tinyprog wrapper"
	chmod 755 "$PREFIX/bin/tinyprog" || die "Failed to chmod tinyprog"
	newpath="$PREFIX/bin:$newpath"
fi

echo
echo
echo
echo "Successfully built and installed all FPGA tools to: $INSTALLDIR"
echo "Please add the following line to your $HOME/.bashrc file:"
echo
echo "export PATH=\"$newpath\""
echo
