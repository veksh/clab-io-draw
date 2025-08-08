import logging
import math
# import re

logger = logging.getLogger(__name__)


class DiagramBuilder:
    """
    Builds diagram elements such as nodes, ports, and links into the Draw.io diagram.
    """

    @staticmethod
    def _round_port_position(x, y):
        """
        Round port positions to avoid floating point precision issues.
        Returns a tuple (x, y) with coordinates rounded to nearest integer.
        """
        return (round(x), round(y))

    def add_ports(self, diagram, styles, _verbose=True):
        """
        Add ports and their connections to the diagram.

        :param diagram: CustomDrawioDiagram instance.
        :param styles: Styles dictionary.
        :param verbose: Enable verbose output.
        """
        logger.debug("Adding ports to nodes...")
        nodes = diagram.nodes
        has_predefined_positions = any(
            isinstance(node.pos_x, int | float) and isinstance(node.pos_y, int | float)
            for node in nodes.values()
        )

        # For fixed positions, first group ports by edge
        if has_predefined_positions:
            # Group links by node and the edge they should connect to
            node_ports_by_edge = {}

            # First pass: determine which edge each link should connect to
            for node in nodes.values():
                node_ports_by_edge[node.name] = {
                    "top": [],
                    "right": [],
                    "bottom": [],
                    "left": [],
                }

                for link in node.get_all_links():
                    target = link.target
                    edge = self._determine_port_edge(node, target, diagram.layout)
                    node_ports_by_edge[node.name][edge].append(link)

            # Second pass: assign positions to ports based on their edge and count
            for node_name in sorted(node_ports_by_edge.keys()):
                edges = node_ports_by_edge[node_name]
                node = nodes[node_name]

                for edge in sorted(edges.keys()):
                    links = edges[edge]
                    if not links:
                        continue

                    # Sort links to ensure consistent and intuitive order
                    if edge in ("top", "bottom"):
                        # For horizontal edges, sort by target X position first, then by target name for consistency
                        links.sort(key=lambda link: (link.target.pos_x, link.target.name))
                    else:  # left or right
                        # For vertical edges, sort by target Y position first, then by target name for consistency
                        links.sort(key=lambda link: (link.target.pos_y, link.target.name))

                    # Distribute ports on the edge
                    self._distribute_ports_on_edge(node, links, edge, styles)
        else:
            # Original port positioning for regular layout
            for node in nodes.values():
                links = node.get_all_links()
                direction_groups = {}
                for link in links:
                    direction = link.direction
                    direction_groups.setdefault(direction, []).append(link)

                for direction, group in direction_groups.items():
                    # Position ports depending on layout and direction
                    if diagram.layout == "vertical":
                        if direction == "downstream":
                            sorted_links = sorted(
                                group,
                                key=lambda link: (link.source.pos_x, link.target.pos_x),
                            )
                            for i, link in enumerate(sorted_links):
                                # Calculate spacing based on whether padding is specified
                                if "port_padding_x" in styles:
                                    total_spacing = styles["port_width"] + styles["port_padding_x"]
                                else:
                                    total_spacing = styles["node_width"] / (len(sorted_links) + 1)
                                port_x = (
                                    node.pos_x
                                    + (i + 1) * total_spacing
                                    - styles["port_width"] / 2
                                )
                                port_y = (
                                    node.pos_y
                                    + styles["node_height"]
                                    - styles["port_height"] / 2
                                )
                                # Round to avoid floating point precision issues
                                port_x = round(port_x)
                                port_y = round(port_y)
                                link.port_pos = self._round_port_position(port_x, port_y)
                        elif direction == "upstream":
                            sorted_links = sorted(
                                group,
                                key=lambda link: (link.source.pos_x, link.target.pos_x),
                            )
                            for i, link in enumerate(sorted_links):
                                # Calculate spacing based on whether padding is specified
                                if "port_padding_x" in styles:
                                    total_spacing = styles["port_width"] + styles["port_padding_x"]
                                else:
                                    total_spacing = styles["node_width"] / (len(sorted_links) + 1)
                                port_x = (
                                    node.pos_x
                                    + (i + 1) * total_spacing
                                    - styles["port_width"] / 2
                                )
                                port_y = node.pos_y - styles["port_height"] / 2
                                # Round to avoid floating point precision issues
                                port_x = round(port_x)
                                port_y = round(port_y)
                                link.port_pos = self._round_port_position(port_x, port_y)
                        else:  # lateral
                            sorted_links = sorted(
                                group,
                                key=lambda link: (link.source.pos_y, link.target.pos_y),
                            )
                            for i, link in enumerate(sorted_links):
                                if link.target.pos_x > link.source.pos_x:
                                    port_x = (
                                        node.pos_x
                                        + styles["node_width"]
                                        - styles["port_width"] / 2
                                    )
                                else:
                                    port_x = node.pos_x - styles["port_width"] / 2
                                # Calculate spacing based on whether padding is specified
                                if "port_padding_y" in styles:
                                    total_spacing = styles["port_height"] + styles["port_padding_y"]
                                else:
                                    total_spacing = styles["node_height"] / (len(sorted_links) + 1)
                                port_y = (
                                    node.pos_y
                                    + (i + 1) * total_spacing
                                    - styles["port_height"] / 2
                                )
                                # Round to avoid floating point precision issues
                                port_x = round(port_x)
                                port_y = round(port_y)
                                link.port_pos = self._round_port_position(port_x, port_y)
                    else:
                        # horizontal layout
                        if direction == "downstream":
                            sorted_links = sorted(
                                group,
                                key=lambda link: (link.source.pos_y, link.target.pos_y),
                            )
                            for i, link in enumerate(sorted_links):
                                port_x = (
                                    node.pos_x
                                    + styles["node_width"]
                                    - styles["port_width"] / 2
                                )
                                # Calculate spacing based on whether padding is specified
                                if "port_padding_y" in styles:
                                    total_spacing = styles["port_height"] + styles["port_padding_y"]
                                else:
                                    total_spacing = styles["node_height"] / (len(sorted_links) + 1)
                                port_y = (
                                    node.pos_y
                                    + (i + 1) * total_spacing
                                    - styles["port_height"] / 2
                                )
                                # Round to avoid floating point precision issues
                                port_x = round(port_x)
                                port_y = round(port_y)
                                link.port_pos = self._round_port_position(port_x, port_y)

                        elif direction == "upstream":
                            sorted_links = sorted(
                                group,
                                key=lambda link: (link.source.pos_y, link.target.pos_y),
                            )
                            for i, link in enumerate(sorted_links):
                                port_x = node.pos_x - styles["port_width"] / 2
                                # Calculate spacing based on whether padding is specified
                                if "port_padding_y" in styles:
                                    total_spacing = styles["port_height"] + styles["port_padding_y"]
                                else:
                                    total_spacing = styles["node_height"] / (len(sorted_links) + 1)
                                port_y = (
                                    node.pos_y
                                    + (i + 1) * total_spacing
                                    - styles["port_height"] / 2
                                )
                                # Round to avoid floating point precision issues
                                port_x = round(port_x)
                                port_y = round(port_y)
                                link.port_pos = self._round_port_position(port_x, port_y)
                        else:  # lateral
                            sorted_links = sorted(
                                group,
                                key=lambda link: (link.source.pos_x, link.target.pos_x),
                            )
                            for i, link in enumerate(sorted_links):
                                if link.target.pos_y > link.source.pos_y:
                                    port_y = (
                                        node.pos_y
                                        + styles["node_height"]
                                        - styles["port_height"] / 2
                                    )
                                else:
                                    port_y = node.pos_y - styles["port_height"] / 2
                                # Calculate spacing based on whether padding is specified
                                if "port_padding_x" in styles:
                                    total_spacing = styles["port_width"] + styles["port_padding_x"]
                                else:
                                    total_spacing = styles["node_width"] / (len(sorted_links) + 1)
                                port_x = (
                                    node.pos_x
                                    + (i + 1) * total_spacing
                                    - styles["port_width"] / 2
                                )
                                # Round to avoid floating point precision issues
                                port_x = round(port_x)
                                port_y = round(port_y)
                                link.port_pos = self._round_port_position(port_x, port_y)

        # stolen from below
        def format_interface_name_port(intf_name):
            # This only affects visual display, not the underlying data used by Grafana
            if styles.get("compact_interface_names", True):
                # Common interface name formats
                if intf_name.lower().startswith("ethernet-"):
                    return "e" + intf_name[9:]
                if intf_name.lower().startswith("ethernet"):
                    return "e" + intf_name[8:]
                # Keep capitalization for capitalized interfaces
                if intf_name.startswith("Ethernet"):
                    return "E" + intf_name[8:]
                # Add more format rules as needed
            return intf_name


        # Create connectors and midpoint connectors
        connector_dict = {}
        processed_connections = set()
        for node in nodes.values():
            downstream_links = node.get_downstream_links()
            lateral_links = node.get_lateral_links()
            node_links = downstream_links + lateral_links

            for link in node_links:
                connection_id = frozenset(
                    {
                        (link.source.name, link.source_intf),
                        (link.target.name, link.target_intf),
                    }
                )
                if connection_id not in processed_connections:
                    processed_connections.add(connection_id)
                    source_cID = f"{link.source.name}:{link.source_intf}:{link.target.name}:{link.target_intf}"
                    #source_label = re.findall(r"\d+", link.source_intf)[-1]
                    source_label = format_interface_name_port(link.source_intf)
                    source_connector_pos = link.port_pos
                    port_width = styles["port_width"]
                    port_height = styles["port_height"]

                    if link.source.name not in connector_dict:
                        connector_dict[link.source.name] = []
                    connector_dict[link.source.name].append(source_cID)

                    target_cID = f"{link.target.name}:{link.target_intf}:{link.source.name}:{link.source_intf}"
                    target_link = diagram.get_target_link(link)
                    target_connector_pos = target_link.port_pos
                    #target_label = re.findall(r"\d+", target_link.source_intf)[-1]
                    target_label = format_interface_name_port(target_link.source_intf)

                    if link.target.name not in connector_dict:
                        connector_dict[link.target.name] = []
                    connector_dict[link.target.name].append(target_cID)

                    # Adjust port positions if mismatch - but only for non-fixed layouts
                    # For fixed positions (has_predefined_positions), the edge-based algorithm 
                    # already handles proper port placement, so skip this adjustment
                    if not has_predefined_positions:
                        source_downstream_links = link.source.get_downstream_links()
                        target_upstream_links = link.target.get_upstream_links()
                        if (
                            diagram.layout == "vertical"
                            and link.source.pos_x == link.target.pos_x
                            and len(source_downstream_links) != len(target_upstream_links)
                        ):
                            if len(source_downstream_links) < len(target_upstream_links):
                                adjusted_x = target_connector_pos[0]
                                source_connector_pos = (adjusted_x, source_connector_pos[1])
                            else:
                                adjusted_x = source_connector_pos[0]
                                target_connector_pos = (adjusted_x, target_connector_pos[1])
                        elif (
                            diagram.layout == "horizontal"
                            and link.source.pos_y == link.target.pos_y
                            and len(source_downstream_links) != len(target_upstream_links)
                        ):
                            if len(source_downstream_links) < len(target_upstream_links):
                                adjusted_y = target_connector_pos[1]
                                source_connector_pos = (source_connector_pos[0], adjusted_y)
                            else:
                                adjusted_y = source_connector_pos[1]
                                target_connector_pos = (target_connector_pos[0], adjusted_y)

                    # Add source and target connector nodes
                    diagram.add_node(
                        id=source_cID,
                        label=source_label,
                        x_pos=source_connector_pos[0],
                        y_pos=source_connector_pos[1],
                        width=port_width,
                        height=port_height,
                        style=styles["port_style"],
                    )

                    diagram.add_node(
                        id=target_cID,
                        label=target_label,
                        x_pos=target_connector_pos[0],
                        y_pos=target_connector_pos[1],
                        width=port_width,
                        height=port_height,
                        style=styles["port_style"],
                    )

                    # Create midpoint connector
                    source_center = (
                        source_connector_pos[0] + port_width / 2,
                        source_connector_pos[1] + port_height / 2,
                    )
                    target_center = (
                        target_connector_pos[0] + port_width / 2,
                        target_connector_pos[1] + port_height / 2,
                    )

                    midpoint_center_x = (source_center[0] + target_center[0]) / 2
                    midpoint_center_y = (source_center[1] + target_center[1]) / 2

                    if styles.get("connector_mid", False):
                        # Place midpoint exactly in the center
                        pass  # midpoint_center_x, midpoint_center_y already set
                    else:
                        # Use deterministic offset based on link endpoints to avoid randomness
                        # Create a consistent offset based on the link characteristics
                        # Use deterministic checksum instead of hash() for consistent results
                        link_names = sorted([link.source.name, link.source_intf, link.target.name, link.target_intf])
                        combined_string = "|".join(link_names)
                        link_hash = sum(ord(c) for c in combined_string)
                        # Use modulo to get consistent offset direction
                        offset_direction = 1 if (link_hash % 2) == 0 else -1
                        offset_magnitude = 15  # Fixed offset magnitude instead of random
                        
                        dx = target_center[0] - source_center[0]
                        dy = target_center[1] - source_center[1]
                        magnitude = (dx**2 + dy**2) ** 0.5
                        if magnitude != 0:
                            direction_dx = dx / magnitude
                            direction_dy = dy / magnitude
                        else:
                            direction_dx = 0
                            direction_dy = 0

                        # Apply deterministic offset perpendicular to the link direction
                        perp_dx = -direction_dy
                        perp_dy = direction_dx
                        midpoint_center_x += perp_dx * offset_magnitude * offset_direction
                        midpoint_center_y += perp_dy * offset_magnitude * offset_direction

                    midpoint_top_left_x = midpoint_center_x - 2
                    midpoint_top_left_y = midpoint_center_y - 2
                    
                    # Round to avoid floating point precision issues
                    midpoint_top_left_x = round(midpoint_top_left_x, 1)
                    midpoint_top_left_y = round(midpoint_top_left_y, 1)

                    midpoint_id = f"mid:{link.source.name}:{link.source_intf}:{link.target.name}:{link.target_intf}"
                    diagram.add_node(
                        id=midpoint_id,
                        label="\u200b",
                        x_pos=midpoint_top_left_x,
                        y_pos=midpoint_top_left_y,
                        width=styles["connector_width"],
                        height=styles["connector_height"],
                        style=styles["connector_style"],
                    )

                    # Helper logic to determine stroke width based on link-speed (link > source node > target node)
                    def _calc_stroke_width(l):
                        lspeed = None
                        if isinstance(getattr(l, 'labels', None), dict):
                            lspeed = l.labels.get('link-speed')
                        if lspeed is None and isinstance(getattr(l.source, 'labels', None), dict):
                            lspeed = l.source.labels.get('link-speed')
                        if lspeed is None and isinstance(getattr(l.target, 'labels', None), dict):
                            lspeed = l.target.labels.get('link-speed')
                        width_map = styles.get('link_line_width', {}) or {}
                        default_w = width_map.get('default', 2)
                        try:
                            default_w = int(default_w)
                        except (ValueError, TypeError):
                            default_w = 2
                        if lspeed is None:
                            return default_w
                        key = str(lspeed).strip()
                        key_upper = key.upper()
                        # direct / upper / case-insensitive match
                        if key in width_map:
                            sw = width_map[key]
                        elif key_upper in width_map:
                            sw = width_map[key_upper]
                        else:
                            sw = next((width_map[k] for k in width_map if k.upper() == key_upper), default_w)
                        try:
                            return int(sw)
                        except (ValueError, TypeError):
                            return default_w

                    stroke_width = _calc_stroke_width(link)
                    mid_style = f"{styles['link_style']}strokeWidth={stroke_width};"

                    diagram.add_link(
                        source=source_cID,
                        target=midpoint_id,
                        style=mid_style,
                        label="rate_s",
                        link_id=f"{source_cID}",
                    )
                    diagram.add_link(
                        source=target_cID,
                        target=midpoint_id,
                        style=mid_style,
                        label="rate_t",
                        link_id=f"{target_cID}",
                    )

        # Create groups for each node + connectors
        for node_name in sorted(connector_dict.keys()):
            connector_ids = connector_dict[node_name]
            group_id = f"group-{node_name}"
            member_objects = connector_ids + [node_name]
            diagram.group_nodes(
                member_objects=member_objects, group_id=group_id, style="group"
            )

    def _determine_port_edge(self, node, target, layout):
        """
        Determine which edge of the node a port should be placed on based on the relative
        position of the target node and layout direction.

        Returns: 'top', 'right', 'bottom', or 'left'
        """
        # Calculate relative positions
        node_center_x = node.pos_x + node.width / 2
        node_center_y = node.pos_y + node.height / 2
        target_center_x = target.pos_x + target.width / 2
        target_center_y = target.pos_y + target.height / 2

        dx = target_center_x - node_center_x
        dy = target_center_y - node_center_y

        if layout == "vertical":
            # In vertical layout, prioritize top/bottom connections
            # Define Y-position threshold for considering nodes at similar height
            y_threshold = node.height * 1.2  # 120% of node height
            if abs(dy) > y_threshold:
                # Target is significantly above or below
                return "top" if dy < 0 else "bottom"
            # Target is roughly at same height, use left/right
            return "left" if dx < 0 else "right"
        else:
            # In horizontal layout, prioritize left/right connections for significant distance
            # Use larger threshold to prefer left/right when possible
            x_threshold = node.width * 1.5  # Increased threshold
            if abs(dx) > x_threshold:
                # Target is significantly left or right
                return "left" if dx < 0 else "right"
            
            # For nodes at similar horizontal positions, use intelligent top/bottom assignment
            # Consider the angle to the target to make a better decision
            angle = math.atan2(dy, abs(dx)) if abs(dx) > 1e-6 else math.pi/2 if dy > 0 else -math.pi/2
            angle_degrees = abs(math.degrees(angle))
            
            # If the angle is steep (close to vertical), prefer top/bottom
            if angle_degrees > 45:  # More vertical than horizontal
                return "top" if dy < 0 else "bottom"
            else:
                # For shallow angles, still prefer top/bottom but distribute better
                # Use a combination of relative position and node name hash for consistency
                if abs(dy) > node.height * 0.2:  # Small threshold for clear direction
                    return "top" if dy < 0 else "bottom"
                else:
                    # Very similar positions - use deterministic distribution
                    # This helps avoid all ports going to the same edge
                    # Use a stable hash based on sorted node names for consistency
                    # Use a more deterministic approach than Python's hash() which can vary
                    names_sorted = sorted([node.name, target.name])
                    combined_string = "|".join(names_sorted)
                    # Use a simple checksum instead of hash() for deterministic results
                    combined_hash = sum(ord(c) for c in combined_string) % 4
                    if combined_hash < 2:
                        return "top"
                    else:
                        return "bottom"

    def _distribute_ports_on_edge(self, node, links, edge, styles):
        """
        Distribute ports with constant spacing (port_padding_x/y), centered as a group on the edge.
        Ensures ports are always evenly distributed along the edge to prevent overlapping.
        """
        port_width = styles["port_width"]
        port_height = styles["port_height"]
        node_width = node.width
        node_height = node.height

        # Number of ports to distribute
        num_ports = len(links)

        if num_ports == 0:
            return

        # Debug for the problematic connection
        debug_node = False
        if debug_node:
            print(f"DISTRIBUTE DEBUG: Node {node.name}, Edge {edge}, Num ports: {num_ports}")
            print(f"  Node dimensions: {node_width}x{node_height}")
            print(f"  Port dimensions: {port_width}x{port_height}")

        if edge in ("left", "right"):
            # Vertical distribution on left/right edges
            if num_ports == 1:
                center_y = node.pos_y + node_height / 2.0
                port_y = round(center_y - port_height / 2)
                port_x = node.pos_x - port_width / 2 if edge == "left" else node.pos_x + node_width - port_width / 2
                links[0].port_pos = self._round_port_position(round(port_x), port_y)
                return

            if "port_padding_y" in styles:
                # Exact constant spacing: distance between adjacent port top-lefts = port_height + padding
                step = port_height + styles["port_padding_y"]  # integer (expected)
                group_height = step * (num_ports - 1)  # distance between first and last centers
                center_y = node.pos_y + node_height / 2.0
                first_center_y = center_y - group_height / 2.0
                first_top_left_y = round(first_center_y - port_height / 2.0)
                for i, link in enumerate(links):
                    port_y = first_top_left_y + i * step
                    port_x = node.pos_x - port_width / 2 if edge == "left" else node.pos_x + node_width - port_width / 2
                    link.port_pos = self._round_port_position(round(port_x), port_y)
                return
            # Fallback: even distribution using available space (original behaviour)
            available_height = node_height * 0.8
            total_spacing = available_height / (num_ports + 1)
            center_y = node.pos_y + node_height / 2.0
            group_height = (num_ports - 1) * total_spacing
            start_y = center_y - group_height / 2.0
            for i, link in enumerate(links):
                port_y = round(start_y + i * total_spacing - port_height / 2)
                port_x = node.pos_x - port_width / 2 if edge == "left" else node.pos_x + node_width - port_width / 2
                link.port_pos = self._round_port_position(round(port_x), port_y)

        elif edge in ("top", "bottom"):
            # Horizontal distribution on top/bottom edges
            if num_ports == 1:
                center_x = node.pos_x + node_width / 2.0
                port_x = round(center_x - port_width / 2)
                port_y = node.pos_y - port_height / 2 if edge == "top" else node.pos_y + node_height - port_height / 2
                links[0].port_pos = self._round_port_position(port_x, round(port_y))
                return

            if "port_padding_x" in styles:
                step = port_width + styles["port_padding_x"]
                group_width = step * (num_ports - 1)
                center_x = node.pos_x + node_width / 2.0
                first_center_x = center_x - group_width / 2.0
                first_top_left_x = round(first_center_x - port_width / 2.0)
                for i, link in enumerate(links):
                    port_x = first_top_left_x + i * step
                    port_y = node.pos_y - port_height / 2 if edge == "top" else node.pos_y + node_height - port_height / 2
                    link.port_pos = self._round_port_position(port_x, round(port_y))
                return
            # Fallback: even distribution using available space
            available_width = node_width * 0.8
            total_spacing = available_width / (num_ports + 1)
            center_x = node.pos_x + node_width / 2.0
            group_width = (num_ports - 1) * total_spacing
            start_x = center_x - group_width / 2.0
            for i, link in enumerate(links):
                port_x = round(start_x + i * total_spacing - port_width / 2)
                port_y = node.pos_y - port_height / 2 if edge == "top" else node.pos_y + node_height - port_height / 2
                link.port_pos = self._round_port_position(port_x, round(port_y))

    # not really used for grafana diagram generation -- "add_port" creates all the links, see above
    def add_links(self, diagram, styles):
        """
        Add links between nodes, with labels if needed.

        :param diagram: CustomDrawioDiagram instance.
        :param styles: Styles dictionary.
        """
        logger.debug("Adding links to diagram...")
        nodes = diagram.nodes
        global_seen_links = set()
        has_predefined_positions = any(
            isinstance(node.pos_x, int | float) and isinstance(node.pos_y, int | float)
            for node in nodes.values()
        )

        # IMPORTANT ADDITION: Calculate port positions even if we don't render them
        # This ensures consistent link placement between port and non-port themes
        # BUT only if we haven't already calculated them with the edge-based algorithm
        if not styles.get("ports", False) and not has_predefined_positions:
            # Calculate virtual port positions that we'll use for entry/exit points
            temp_port_styles = styles.copy()
            temp_port_styles["port_width"] = styles.get("port_width", 10)
            temp_port_styles["port_height"] = styles.get("port_height", 10)

            for node in nodes.values():
                links = node.get_all_links()
                if has_predefined_positions:
                    # Group links by edge just like we do in add_ports()
                    node_ports_by_edge = {
                        "top": [],
                        "right": [],
                        "bottom": [],
                        "left": [],
                    }

                    for link in links:
                        target = link.target
                        edge = self._determine_port_edge(node, target, diagram.layout)
                        node_ports_by_edge[edge].append(link)

                    # Distribute ports along each edge
                    for edge in sorted(node_ports_by_edge.keys()):
                        edge_links = node_ports_by_edge[edge]
                        if edge_links:
                            # Sort links the same way we would with ports
                            if edge in ("top", "bottom"):
                                edge_links.sort(key=lambda link: link.target.pos_x)
                            else:  # left or right
                                edge_links.sort(key=lambda link: link.target.pos_y)

                            # Assign virtual port positions
                            self._distribute_ports_on_edge(
                                node, edge_links, edge, temp_port_styles
                            )
                else:
                    # Handle standard layout positioning as done in add_ports()
                    direction_groups = {}
                    for link in links:
                        direction = link.direction
                        direction_groups.setdefault(direction, []).append(link)

                    for direction, group in direction_groups.items():
                        # Position ports depending on layout and direction - copying logic from add_ports()
                        if diagram.layout == "vertical":
                            if direction == "downstream":
                                sorted_links = sorted(
                                    group,
                                    key=lambda link: (
                                        link.source.pos_x,
                                        link.target.pos_x,
                                    ),
                                )
                                num_links = len(sorted_links)
                                spacing = temp_port_styles["node_width"] / (
                                    num_links + 1
                                )
                                for i, link in enumerate(sorted_links):
                                    port_x = (
                                        node.pos_x
                                        + (i + 1) * spacing
                                        - temp_port_styles["port_width"] / 2
                                    )
                                    port_y = (
                                        node.pos_y
                                        + temp_port_styles["node_height"]
                                        - temp_port_styles["port_height"] / 2
                                    )
                                    link.port_pos = self._round_port_position(port_x, port_y)
                            elif direction == "upstream":
                                sorted_links = sorted(
                                    group,
                                    key=lambda link: (
                                        link.source.pos_x,
                                        link.target.pos_x,
                                    ),
                                )
                                num_links = len(sorted_links)
                                spacing = temp_port_styles["node_width"] / (
                                    num_links + 1
                                )
                                for i, link in enumerate(sorted_links):
                                    port_x = (
                                        node.pos_x
                                        + (i + 1) * spacing
                                        - temp_port_styles["port_width"] / 2
                                    )
                                    port_y = (
                                        node.pos_y - temp_port_styles["port_height"] / 2
                                    )
                                    link.port_pos = self._round_port_position(port_x, port_y)
                            else:  # lateral
                                sorted_links = sorted(
                                    group,
                                    key=lambda link: (
                                        link.source.pos_y,
                                        link.target.pos_y,
                                    ),
                                )
                                num_links = len(sorted_links)
                                spacing = temp_port_styles["node_height"] / (
                                    num_links + 1
                                )
                                for i, link in enumerate(sorted_links):
                                    if link.target.pos_x > link.source.pos_x:
                                        port_x = (
                                            node.pos_x
                                            + temp_port_styles["node_width"]
                                            - temp_port_styles["port_width"] / 2
                                        )
                                    else:
                                        port_x = (
                                            node.pos_x
                                            - temp_port_styles["port_width"] / 2
                                        )
                                    port_y = (
                                        node.pos_y
                                        + (i + 1) * spacing
                                        - temp_port_styles["port_height"] / 2
                                    )
                                    link.port_pos = self._round_port_position(port_x, port_y)
                        else:
                            # horizontal layout
                            if direction == "downstream":
                                sorted_links = sorted(
                                    group,
                                    key=lambda link: (
                                        link.source.pos_y,
                                        link.target.pos_y,
                                    ),
                                )
                                num_links = len(sorted_links)
                                spacing = temp_port_styles["node_height"] / (
                                    num_links + 1
                                )
                                for i, link in enumerate(sorted_links):
                                    port_x = (
                                        node.pos_x
                                        + temp_port_styles["node_width"]
                                        - temp_port_styles["port_width"] / 2
                                    )
                                    port_y = (
                                        node.pos_y
                                        + (i + 1) * spacing
                                        - temp_port_styles["port_height"] / 2
                                    )
                                    link.port_pos = self._round_port_position(port_x, port_y)
                            elif direction == "upstream":
                                sorted_links = sorted(
                                    group,
                                    key=lambda link: (
                                        link.source.pos_y,
                                        link.target.pos_y,
                                    ),
                                )
                                num_links = len(sorted_links)
                                spacing = temp_port_styles["node_height"] / (
                                    num_links + 1
                                )
                                for i, link in enumerate(sorted_links):
                                    port_x = (
                                        node.pos_x - temp_port_styles["port_width"] / 2
                                    )
                                    port_y = (
                                        node.pos_y
                                        + (i + 1) * spacing
                                        - temp_port_styles["port_height"] / 2
                                    )
                                    link.port_pos = self._round_port_position(port_x, port_y)
                            else:  # lateral
                                sorted_links = sorted(
                                    group,
                                    key=lambda link: (
                                        link.source.pos_x,
                                        link.target.pos_x,
                                    ),
                                )
                                num_links = len(sorted_links)
                                spacing = temp_port_styles["node_width"] / (
                                    num_links + 1
                                )
                                for i, link in enumerate(sorted_links):
                                    if link.target.pos_y > link.source.pos_y:
                                        port_y = (
                                            node.pos_y
                                            + temp_port_styles["node_height"]
                                            - temp_port_styles["port_height"] / 2
                                        )
                                    else:
                                        port_y = (
                                            node.pos_y
                                            - temp_port_styles["port_height"] / 2
                                        )
                                    port_x = (
                                        node.pos_x
                                        + (i + 1) * spacing
                                        - temp_port_styles["port_width"] / 2
                                    )
                                    link.port_pos = self._round_port_position(port_x, port_y)

        # Function to format interface names to be more compact if enabled
        def format_interface_name(intf_name):
            # This only affects visual display, not the underlying data used by Grafana
            if styles.get("compact_interface_names", True):
                # Common interface name formats
                if intf_name.lower().startswith("ethernet-"):
                    return "e" + intf_name[9:]
                if intf_name.lower().startswith("ethernet"):
                    return "e" + intf_name[8:]
                # Keep capitalization for capitalized interfaces
                if intf_name.startswith("Ethernet"):
                    return "E" + intf_name[8:]
                # Add more format rules as needed
            return intf_name

        # Configure font size for labels
        src_label_style = styles.get("src_label_style", "")
        trgt_label_style = styles.get("trgt_label_style", "")

        for node in nodes.values():
            downstream_links = node.get_downstream_links()
            lateral_links = node.get_lateral_links()
            all_links = downstream_links + lateral_links

            filtered_links = []
            for link in all_links:
                source_id = f"{link.source.name}:{link.source_intf}"
                target_id = f"{link.target.name}:{link.target_intf}"
                link_pair = tuple(sorted([source_id, target_id]))
                if link_pair not in global_seen_links:
                    global_seen_links.add(link_pair)
                    filtered_links.append(link)

            target_groups = {}
            for link in filtered_links:
                tgt = link.target
                target_groups.setdefault(tgt, []).append(link)

            for _tgt, group in target_groups.items():
                for i, link in enumerate(group):
                    source_x, source_y = link.source.pos_x, link.source.pos_y
                    target_x, target_y = link.target.pos_x, link.target.pos_y

                    if has_predefined_positions:
                        # For fixed positions, determine entry/exit points based on port positions
                        if hasattr(link, "port_pos") and link.port_pos:
                            source_edge = self._determine_port_edge(
                                link.source, link.target, diagram.layout
                            )
                            target_edge = self._determine_port_edge(
                                link.target, link.source, diagram.layout
                            )

                            # Set entry/exit percentages based on edge
                            if source_edge == "top":
                                exitY, exitX = 0, 0.5
                            elif source_edge == "right":
                                exitY, exitX = 0.5, 1
                            elif source_edge == "bottom":
                                exitY, exitX = 1, 0.5
                            else:  # left
                                exitY, exitX = 0.5, 0

                            if target_edge == "top":
                                entryY, entryX = 0, 0.5
                            elif target_edge == "right":
                                entryY, entryX = 0.5, 1
                            elif target_edge == "bottom":
                                entryY, entryX = 1, 0.5
                            else:  # left
                                entryY, entryX = 0.5, 0
                            if (
                                abs(link.source.pos_y - link.target.pos_y) < 10
                                and len(group) > 1
                            ):
                                # Distribute links vertically for nodes at same level
                                spread = 0.4 / len(
                                    group
                                )  # Use 40% of the node height for distribution
                                offset = (i - (len(group) - 1) / 2) * spread

                                # Adjust entry/exit Y positions
                                if source_edge in ["left", "right"]:
                                    exitY = 0.5 + offset

                                if target_edge in ["left", "right"]:
                                    entryY = 0.5 + offset
                        else:
                            # Fallback if no port_pos
                            entryX, entryY, exitX, exitY = (
                                self._calculate_entry_exit_for_fixed_layout(link)
                            )
                    else:
                        # Original link entry/exit point calculation
                        left_to_right = source_x < target_x
                        above_to_below = source_y < target_y

                        step = (
                            0.5
                            if len(group) == 1
                            else 0.25 + 0.5 * (i / (len(group) - 1))
                        )

                        if diagram.layout == "horizontal":
                            if link.level_diff > 0:
                                entryX, exitX = (0, 1) if left_to_right else (1, 0)
                                entryY = exitY = step
                            else:
                                if above_to_below:
                                    entryY, exitY = (0, 1)
                                else:
                                    entryY, exitY = (1, 0)
                                entryX = exitX = step
                        else:  # vertical layout
                            if link.level_diff > 0:
                                entryY, exitY = (0, 1) if above_to_below else (1, 0)
                                entryX = exitX = step
                            else:
                                if left_to_right:
                                    entryX, exitX = (0, 1)
                                else:
                                    entryX, exitX = (1, 0)
                                entryY = exitY = step

                    style = f"{styles['link_style']}entryY={entryY};exitY={exitY};entryX={entryX};exitX={exitX};"
                    # Override strokeWidth based on link-speed label (link > source node > target node)
                    link_speed = None
                    if isinstance(getattr(link, 'labels', None), dict):
                        link_speed = link.labels.get('link-speed')
                    if link_speed is None and isinstance(getattr(link.source, 'labels', None), dict):
                        link_speed = link.source.labels.get('link-speed')
                    if link_speed is None and isinstance(getattr(link.target, 'labels', None), dict):
                        link_speed = link.target.labels.get('link-speed')
                    width_map = styles.get('link_line_width', {}) or {}
                    default_width = width_map.get('default', 2)
                    try:
                        default_width = int(default_width)
                    except (ValueError, TypeError):
                        default_width = 2
                    stroke_width = default_width
                    if link_speed is not None:
                        key = str(link_speed).strip()
                        key_upper = key.upper()
                        # Try direct, upper, then case-insensitive match
                        if key in width_map:
                            stroke_width = width_map[key]
                        elif key_upper in width_map:
                            stroke_width = width_map[key_upper]
                        else:
                            for k in width_map:
                                if k.upper() == key_upper:
                                    stroke_width = width_map[k]
                                    break
                    try:
                        stroke_width = int(stroke_width)
                    except (ValueError, TypeError):
                        stroke_width = default_width
                    style += f"strokeWidth={stroke_width};"

                    source_label_id = f"label:{link.source.name}:{link.source_intf}"
                    target_label_id = f"label:{link.target.name}:{link.target_intf}"

                    if not styles.get("default_labels", False):
                        (
                            (source_label_x, source_label_y),
                            (target_label_x, target_label_y),
                        ) = link.get_label_positions(
                            entryX, entryY, exitX, exitY, styles
                        )

                        diagram.add_link(
                            link_id=f"link:{link.source.name}:{link.source_intf}:{link.target.name}:{link.target_intf}",
                            source=link.source.name,
                            target=link.target.name,
                            style=style,
                        )

                        diagram.add_node(
                            id=source_label_id,
                            label=f"{format_interface_name(link.source_intf)}",
                            x_pos=source_label_x,
                            y_pos=source_label_y,
                            width=styles["label_width"],
                            height=styles["label_height"],
                            style=src_label_style,
                        )

                        diagram.add_node(
                            id=target_label_id,
                            label=f"{format_interface_name(link.target_intf)}",
                            x_pos=target_label_x,
                            y_pos=target_label_y,
                            width=styles["label_width"],
                            height=styles["label_height"],
                            style=trgt_label_style,
                        )
                    else:
                        diagram.add_link(
                            link_id=f"link:{link.source.name}:{link.source_intf}:{link.target.name}:{link.target_intf}",
                            source=link.source.name,
                            target=link.target.name,
                            src_label=format_interface_name(link.source_intf),
                            trgt_label=format_interface_name(link.target_intf),
                            src_label_style=src_label_style,
                            trgt_label_style=trgt_label_style,
                            style=style,
                        )

    def _calculate_entry_exit_for_fixed_layout(self, link):
        """
        Calculate appropriate entry and exit points for links between nodes with fixed positions.
        Returns (entryX, entryY, exitX, exitY) tuple.
        """
        source = link.source
        target = link.target

        # Calculate center points of nodes
        source_center_x = source.pos_x + source.width / 2
        source_center_y = source.pos_y + source.height / 2
        target_center_x = target.pos_x + target.width / 2
        target_center_y = target.pos_y + target.height / 2

        # Calculate angle between centers
        dx = target_center_x - source_center_x
        dy = target_center_y - source_center_y
        angle_source_to_target = math.atan2(dy, dx)
        angle_target_to_source = math.atan2(-dy, -dx)

        # Determine exit point from source based on angle
        if -math.pi / 4 <= angle_source_to_target <= math.pi / 4:
            # Exit from right of source
            exitX, exitY = 1, 0.5
        elif math.pi / 4 <= angle_source_to_target <= 3 * math.pi / 4:
            # Exit from bottom of source
            exitX, exitY = 0.5, 1
        elif (
            angle_source_to_target >= 3 * math.pi / 4
            or angle_source_to_target <= -3 * math.pi / 4
        ):
            # Exit from left of source
            exitX, exitY = 0, 0.5
        else:
            # Exit from top of source
            exitX, exitY = 0.5, 0

        # Determine entry point to target based on angle
        if -math.pi / 4 <= angle_target_to_source <= math.pi / 4:
            # Enter from right of target
            entryX, entryY = 1, 0.5
        elif math.pi / 4 <= angle_target_to_source <= 3 * math.pi / 4:
            # Enter from bottom of target
            entryX, entryY = 0.5, 1
        elif (
            angle_target_to_source >= 3 * math.pi / 4
            or angle_target_to_source <= -3 * math.pi / 4
        ):
            # Enter from left of target
            entryX, entryY = 0, 0.5
        else:
            # Enter from top of target
            entryX, entryY = 0.5, 0

        return entryX, entryY, exitX, exitY

    def add_nodes(self, diagram, nodes, styles):
        """
        Add nodes to the diagram.

        :param diagram: CustomDrawioDiagram instance.
        :param nodes: Dictionary of node_name -> Node instances.
        :param styles: Styles dictionary.
        """
        logger.debug("Adding nodes to diagram...")
        base_style = styles["base_style"]
        custom_styles = styles["custom_styles"]
        icon_to_group_mapping = styles["icon_to_group_mapping"]

        for node in nodes.values():
            if node.graph_icon in icon_to_group_mapping:
                group = icon_to_group_mapping[node.graph_icon]
            else:
                # Fallback heuristics
                if "client" in node.name:
                    group = "server"
                elif "leaf" in node.name:
                    group = "leaf"
                elif "spine" in node.name:
                    group = "spine"
                elif "dcgw" in node.name:
                    group = "dcgw"
                else:
                    group = "default"

            style = custom_styles.get(group, base_style)
            x_pos, y_pos = node.pos_x, node.pos_y
            diagram.add_node(
                id=node.name,
                label=node.label,
                x_pos=x_pos,
                y_pos=y_pos,
                style=style,
                width=node.width,
                height=node.height,
            )
