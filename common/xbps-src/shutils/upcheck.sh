upcheck() {
	# a little glue for the python script
	local update_override="$XBPS_SRCPKGDIR/$XBPS_TARGET_PKG/update"

    if [ -r $update_override ]; then
        . $update_override
        if [ "$XBPS_UPDATE_CHECK_VERBOSE" ]; then
            msg_normal "using $XBPS_TARGET_PKG/update overrides\n" 1>&2
        fi
    elif [ -z "$distfiles" ]; then
        if [ "$XBPS_UPDATE_CHECK_VERBOSE" ]; then
            msg_normal "No distfiles found for ${pkgname}\n" 1>&2
        fi
        return 0
    fi

	export sourcepkg homepage distfiles site pkgname pattern ignore version single_directory vdprefix vdsuffix

	if ! command -v python3 &>/dev/null; then
		msg_error "python3 needed to run this" 1>&2
		return 0
	fi
	[ -r "${XBPS_COMMONDIR}/scripts/update-check.py" ] && python3 -W ignore "${XBPS_COMMONDIR}/scripts/update-check.py"
}