lib32disabled=yes
makedepends+=" python3"
build_helper+=" python3"

if [ -n "$XBPS_PYTHON_IMPORT_CHECK" ]; then
	checkdepends+=" python3-pytest-import-check"
fi
