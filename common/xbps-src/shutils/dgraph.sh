hostmakedep=darksalmon
makedep=yellowgreen
rdep=lightgrey

dgraph_node() {
	local id label
	id="${1}"
	label="${2}"
	echo "	${id} [label=\"${label}\"];"
}

dgraph_edge() {
	local node_from node_to
	node_from="${1}"
	node_to="${2}"
	colour="${3}"

	case $colour in
		host) colour=darksalmon ;;
		make) colour=yellowgreen ;;
		*) colour= ;;
	esac

	if [ -z "$colour" ]; then
		echo "	${node_from} -> ${node_to};"
	else
		echo "	${node_from} -> ${node_to} [color=${colour}];"
	fi
}

dgraph_pkg() {
	local pkg=$1 count=$2

	if [[ ! -v nodes[$pkg] ]]; then
		dgraph_node $count $pkg
		nodes[$pkg]=$count
		count=$((count + 1))
	fi

	for d in $hostmakedepends; do
		# XBPS_TARGET_PKG=$d read_pkg ignore-problems
		dgraph_pkg $d $count
		dgraph_edge ${nodes[$pkg]} ${nodes[$d]} host
	done

	for d in $makedepends; do
		# XBPS_TARGET_PKG=$d read_pkg ignore-problems
		dgraph_pkg $d $count
		dgraph_edge ${nodes[$pkg]} ${nodes[$d]} make
	done

	for d in $depends; do
		# XBPS_TARGET_PKG=$d read_pkg ignore-problems
		dgraph_pkg $d $count
		dgraph_edge ${nodes[$pkg]} ${nodes[$d]} run
	done
}

dgraph() {
	declare -A nodes

	echo "digraph pkg_depends {
	graph [fontname=\"Sans\",nodesep=\".1\",rankdir=\"LR\",ranksep=\".1\",ratio=\"compress\",splines=\"polyline\",label=\"[xbps-src] ${XBPS_TARGET_PKG} full dependency graph\"];
	edge [arrowhead=\"vee\",arrowsize=\".4\",constraint=\"true\",fontname=\"Sans\",fontsize=\"8\"];
	node [fontname=\"Sans\",fontsize=\"8\",height=\".1\",shape=\"ellipse\",width=\".1\"];"

	dgraph_pkg $XBPS_TARGET_PKG 0

	echo "}"
}
