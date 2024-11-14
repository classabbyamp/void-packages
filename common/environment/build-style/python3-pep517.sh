hostmakedepends+=" python3-build python3-installer"
lib32disabled=yes
build_helper+=" python3"

if [ -n "$XBPS_PYTHON_IMPORT_CHECK" ]; then
	checkdepends+=" python3-pytest-import-check"
fi
