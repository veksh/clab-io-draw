import logging

from clab_io_draw.core.models.link import Link
from clab_io_draw.core.models.node import Node

logger = logging.getLogger(__name__)


class NodeLinkBuilder:
    """
    Builds Node and Link objects from containerlab topology data and styling information.
    """

    def __init__(
        self, containerlab_data: dict, styles: dict, prefix: str, lab_name: str
    ):
        """
        :param containerlab_data: Parsed containerlab topology data.
        :param styles: Dictionary of style parameters.
        :param prefix: Prefix used in node names.
        :param lab_name: Name of the lab.
        """
        self.containerlab_data = containerlab_data
        self.styles = styles
        self.prefix = prefix
        self.lab_name = lab_name
        # Index to resolve short (pre-dot) names in link endpoints to full node names
        self._nodes_by_short_label = {}

    def format_node_name(self, base_name: str) -> str:
        """Format node name unless it is already a fully-qualified name.

        If the source topology already supplies FQDN-like names (contains a dot),
        keep them as-is so that dataRefs can use the full name directly.
        """
        # If already fully-qualified (contains a dot), do NOT prefix
        if "." in base_name:
            return base_name
        if not self.prefix:
            return base_name
        return f"{self.prefix}-{self.lab_name}-{base_name}"

    def build_nodes_and_links(self):
        """
        Build Node and Link objects from the provided containerlab data.

        :return: A tuple (nodes_dict, links_list)
        """
        logger.debug("Building nodes...")
        nodes = self._build_nodes()
        logger.debug("Building links...")
        links = self._build_links(nodes)
        return nodes, links

    def _build_nodes(self):
        """
        Internal method to build Node instances from containerlab topology data.

        :return: Dictionary of node_name -> Node
        """
        nodes_from_clab = self.containerlab_data["topology"]["nodes"]

        node_width = self.styles.get("node_width", 75)
        node_height = self.styles.get("node_height", 75)
        base_style = self.styles.get("base_style", "")

        nodes = {}
        for node_name, node_data in nodes_from_clab.items():
            formatted_node_name = self.format_node_name(node_name)

            labels = node_data.get("labels", {})

            # Determine display label: normally first component pre-dot, but if metric-host present keep full name
            if "metric-host" in labels:
                display_label = node_name  # preserve full name
            else:
                display_label = node_name.split(".")[0]

            # Extract position from graph-posX and graph-posY labels if available
            pos_x = node_data.get("pos_x", "")
            pos_y = node_data.get("pos_y", "")

            if "graph-posX" in labels:
                pos_x = labels["graph-posX"]
            if "graph-posY" in labels:
                pos_y = labels["graph-posY"]

            width = self.styles.get("node_width", node_width)
            height = self.styles.get("node_height", node_height)
            if "graph-width" in labels:
                try:
                    width = int(labels["graph-width"])
                except (ValueError, TypeError):
                    pass
            if "graph-height" in labels:
                try:
                    height = int(labels["graph-height"])
                except (ValueError, TypeError):
                    pass

            node = Node(
                name=formatted_node_name,
                label=display_label,  # shortened unless metric-host
                kind=node_data.get("kind", ""),
                mgmt_ipv4=node_data.get("mgmt_ipv4", ""),
                graph_level=labels.get("graph-level", None),
                graph_icon=labels.get("graph-icon", None),
                labels=labels,
                base_style=base_style,
                custom_style=self.styles.get(node_data.get("kind", ""), ""),
                pos_x=pos_x,
                pos_y=pos_y,
                width=width,
                height=height,
                group=node_data.get("group", ""),
            )
            nodes[formatted_node_name] = node
            self._nodes_by_short_label.setdefault(display_label.split(".")[0], []).append(node)

        return nodes

    def _resolve_endpoint_node(self, endpoint_name: str, nodes: dict):
        """Resolve a link endpoint base name to a Node.

        Endpoints in links may use the short name (first component before '.') while
        the node dictionary keys may contain fully-qualified names.
        """
        # Direct match (already full name)
        if endpoint_name in nodes:
            return nodes[endpoint_name]
        # Try to match by short label
        candidates = self._nodes_by_short_label.get(endpoint_name)
        if candidates:
            if len(candidates) > 1:
                logger.warning(
                    "Multiple nodes matched short endpoint name '%s'; using first: %s",
                    endpoint_name,
                    [n.name for n in candidates],
                )
            return candidates[0]
        return None

    def _build_links(self, nodes):
        """
        Internal method to build Link instances and attach them to their respective nodes.

        :param nodes: Dictionary of node_name -> Node
        :return: List of Link objects
        """
        links_from_clab = []
        for link in self.containerlab_data["topology"].get("links", []):
            endpoints = link.get("endpoints")
            if endpoints:
                source_node_name, source_intf = endpoints[0].split(":")
                target_node_name, target_intf = endpoints[1].split(":")

                # Resolve against existing nodes (short or full)
                source_node = self._resolve_endpoint_node(source_node_name, nodes)
                target_node = self._resolve_endpoint_node(target_node_name, nodes)

                if source_node and target_node:
                    links_from_clab.append(
                        {
                            "source": source_node.name,
                            "target": target_node.name,
                            "source_intf": source_intf,
                            "target_intf": target_intf,
                            "labels": link.get("labels", {}),
                        }
                    )
                else:
                    logger.warning(
                        "Unable to resolve link endpoints '%s' or '%s' to nodes",
                        source_node_name,
                        target_node_name,
                    )

        links = []
        for link_data in links_from_clab:
            source_node = nodes.get(link_data["source"])
            target_node = nodes.get(link_data["target"])

            if source_node and target_node:
                downstream_link = Link(
                    source=source_node,
                    target=target_node,
                    source_intf=link_data.get("source_intf", ""),
                    target_intf=link_data.get("target_intf", ""),
                    base_style=self.styles.get("base_style", ""),
                    link_style=self.styles.get("link_style", ""),
                    src_label_style=self.styles.get("src_label_style", ""),
                    trgt_label_style=self.styles.get("trgt_label_style", ""),
                    direction="downstream",
                    labels=link_data.get("labels", {}),
                )
                upstream_link = Link(
                    source=target_node,
                    target=source_node,
                    source_intf=link_data.get("target_intf", ""),
                    target_intf=link_data.get("source_intf", ""),
                    base_style=self.styles.get("base_style", ""),
                    link_style=self.styles.get("link_style", ""),
                    src_label_style=self.styles.get("src_label_style", ""),
                    trgt_label_style=self.styles.get("trgt_label_style", ""),
                    direction="upstream",
                    labels=link_data.get("labels", {}),
                )
                links.append(downstream_link)
                links.append(upstream_link)

                source_node.add_link(downstream_link)
                target_node.add_link(upstream_link)

        return links
