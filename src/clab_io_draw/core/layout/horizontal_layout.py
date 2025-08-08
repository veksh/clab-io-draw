import logging
from collections import defaultdict

from clab_io_draw.core.layout.layout_manager import LayoutManager

logger = logging.getLogger(__name__)


class HorizontalLayout(LayoutManager):
    def apply(self, diagram, verbose=False) -> None:
        # pylint: disable=attribute-defined-outside-init
        logger.debug("Applying iterative barycenter layout (horizontal)...")
        self.diagram = diagram
        self.verbose = verbose

        nodes_by_level = defaultdict(list)
        for n in self.diagram.nodes.values():
            nodes_by_level[n.graph_level].append(n)

        sorted_levels = sorted(nodes_by_level.keys())

        # Initial positioning (uses default style height as before)
        for level in sorted_levels:
            nodes_by_level[level].sort(key=lambda nd: nd.name)
            for i, nd in enumerate(nodes_by_level[level]):
                # Position nodes with proper spacing between them (node_height + padding)
                total_spacing = self.diagram.styles["node_height"] + self.diagram.styles["padding_y"]
                nd.pos_y = float(100 + i * total_spacing)

        def get_connected_pairs(level_nodes):
            """Get pairs of nodes in the same level that are directly connected."""
            pairs = []
            for i, node1 in enumerate(level_nodes):
                for node2 in level_nodes[i + 1 :]:
                    if node2 in node1.get_neighbors():
                        pairs.append((node1, node2))
            return pairs

        def is_position_between_connected_nodes(pos, node, level_nodes):
            """Check if a position would place the node between connected nodes."""
            connected_pairs = get_connected_pairs(level_nodes)
            for n1, n2 in connected_pairs:
                if n1 != node and n2 != node:
                    min_y, max_y = min(n1.pos_y, n2.pos_y), max(n1.pos_y, n2.pos_y)
                    if min_y < pos < max_y:
                        return True
            return False

        def find_valid_positions(node, level_nodes, barycenter):
            """Find all valid positions, prioritizing those that don't create crossings."""
            positions = []

            connected_nodes = set(node.get_neighbors())
            same_level_connected = [n for n in level_nodes if n in connected_nodes]

            existing_positions = sorted([n.pos_y for n in level_nodes if n != node])
            if not existing_positions:
                return [barycenter]

            # Consider positions before first node
            total_spacing = self.diagram.styles["node_height"] + self.diagram.styles["padding_y"]
            positions.append(existing_positions[0] - total_spacing)

            # Consider positions after each node
            for pos in existing_positions:
                positions.append(pos + total_spacing)

            # Add positions next to connected nodes
            if same_level_connected:
                for connected_node in same_level_connected:
                    total_spacing = self.diagram.styles["node_height"] + self.diagram.styles["padding_y"]
                    positions.append(connected_node.pos_y + total_spacing)
                    positions.append(connected_node.pos_y - total_spacing)

            # Remove invalid positions
            min_spacing = (self.diagram.styles["node_height"] + self.diagram.styles["padding_y"]) * 0.9
            valid_positions = []
            for pos in sorted(set(positions)):
                if all(
                    abs(pos - other_pos) >= min_spacing
                    for other_pos in existing_positions
                ):
                    valid_positions.append(pos)

            # Sort positions by priority
            return sorted(
                valid_positions,
                key=lambda p: (
                    is_position_between_connected_nodes(p, node, level_nodes),
                    abs(p - barycenter),
                ),
            )

        def compute_barycenter(node):
            """Compute weighted barycenter of all connected nodes."""
            positions = []
            weights = []

            for nbr in node.get_neighbors():
                try:
                    pos = float(nbr.pos_y)
                    # Give higher weight to same-level connections
                    weight = 2.0 if nbr.graph_level == node.graph_level else 1.0
                    positions.append(pos)
                    weights.append(weight)
                except (TypeError, ValueError):
                    continue

            if positions:
                return sum(
                    p * w for p, w in zip(positions, weights, strict=False)
                ) / sum(weights)
            return node.pos_y

        def reposition_level(level_nodes):
            """Position nodes in a level while avoiding problematic placements."""
            nodes_to_position = sorted(
                level_nodes, key=lambda n: len(list(n.get_neighbors())), reverse=True
            )

            positioned = []
            for node in nodes_to_position:
                barycenter = compute_barycenter(node)
                valid_positions = find_valid_positions(node, positioned, barycenter)

                if valid_positions:
                    node.pos_y = valid_positions[0]
                else:
                    if positioned:
                        node.pos_y = (
                            max(n.pos_y for n in positioned)
                            + self.diagram.styles["padding_y"]
                        )
                    else:
                        node.pos_y = barycenter

                positioned.append(node)

        # Main layout iterations
        num_passes = 4
        for _iter in range(num_passes):
            for level in sorted_levels:
                reposition_level(nodes_by_level[level])

            for level in reversed(sorted_levels):
                reposition_level(nodes_by_level[level])

        # Assign X positions with proper horizontal spacing
        for level in sorted_levels:
            for node in nodes_by_level[level]:
                total_spacing = self.diagram.styles["node_width"] + self.diagram.styles["padding_x"]
                node.pos_x = float(100 + level * total_spacing)

        self._center_align_nodes(nodes_by_level)
        self._adjust_intermediary_nodes(diagram)

        # NEW: repack nodes per level using actual heights so padding_y is respected
        self._pack_variable_heights(nodes_by_level)

        logger.debug("Iterative barycenter layout complete (horizontal).")

    def _center_align_nodes(self, nodes_by_level):
        # pylint: disable=invalid-name
        sorted_levels = sorted(nodes_by_level.keys())
        global_center = 300.0

        prev_center = None
        for level in sorted_levels:
            level_nodes = nodes_by_level[level]
            if not level_nodes:
                continue
            # Center by node visual centers
            min_center = min(nd.pos_y + (float(nd.height) / 2.0 if nd.height else 0) for nd in level_nodes)
            max_center = max(nd.pos_y + (float(nd.height) / 2.0 if nd.height else 0) for nd in level_nodes)
            col_center = (min_center + max_center) / 2.0

            if prev_center is None:
                offset = global_center - col_center
                for nd in level_nodes:
                    nd.pos_y += offset
                min_center = min(nd.pos_y + (float(nd.height) / 2.0 if nd.height else 0) for nd in level_nodes)
                max_center = max(nd.pos_y + (float(nd.height) / 2.0 if nd.height else 0) for nd in level_nodes)
                col_center = (min_center + max_center) / 2.0
                prev_center = col_center
            else:
                offset = prev_center - col_center
                for nd in level_nodes:
                    nd.pos_y += offset
                min_center = min(nd.pos_y + (float(nd.height) / 2.0 if nd.height else 0) for nd in level_nodes)
                max_center = max(nd.pos_y + (float(nd.height) / 2.0 if nd.height else 0) for nd in level_nodes)
                col_center = (min_center + max_center) / 2.0
                prev_center = col_center

    def _adjust_intermediary_nodes(self, diagram, offset=100.0):
        # pylint: disable=invalid-name
        all_links = diagram.get_links_from_nodes()
        nodes = list(diagram.nodes.values())

        for nd in nodes:
            nd.half_w = float(nd.width) / 2.0 if nd.width else 20.0
            nd.half_h = float(nd.height) / 2.0 if nd.height else 20.0

        for link in all_links:
            A = link.source
            B = link.target

            if abs(A.pos_y - B.pos_y) < 1e-5:
                left_x = min(A.pos_x, B.pos_x)
                right_x = max(A.pos_x, B.pos_x)
                for N in nodes:
                    if N not in (A, B):
                        Ny_top = N.pos_y - N.half_h
                        Ny_bot = N.pos_y + N.half_h
                        if Ny_top <= A.pos_y <= Ny_bot:
                            Nx_left = N.pos_x - N.half_w
                            Nx_right = N.pos_x + N.half_w
                            if Nx_left < right_x and Nx_right > left_x:
                                N.pos_y -= offset

            elif abs(A.pos_x - B.pos_x) < 1e-5:
                top_y = min(A.pos_y, B.pos_y)
                bot_y = max(A.pos_y, B.pos_y)
                for N in nodes:
                    if N not in (A, B):
                        Nx_left = N.pos_x - N.half_w
                        Nx_right = N.pos_x + N.half_w
                        if Nx_left <= A.pos_x <= Nx_right:
                            Ny_top = N.pos_y - N.half_h
                            Ny_bot = N.pos_y + N.half_h
                            if Ny_top < bot_y and Ny_bot > top_y:
                                N.pos_x -= offset

    # NEW helper
    def _pack_variable_heights(self, nodes_by_level):
        """Repack nodes in each level so vertical gaps equal padding_y even with per-node custom heights."""
        padding = self.diagram.styles.get("padding_y", 0)
        for _level, level_nodes in nodes_by_level.items():  # _level is unused but kept for clarity
            if len(level_nodes) < 2:
                continue
            level_nodes.sort(key=lambda n: n.pos_y)
            orig_min = min(n.pos_y for n in level_nodes)
            orig_max = max(n.pos_y + n.height for n in level_nodes)
            orig_center = (orig_min + orig_max) / 2.0
            cursor = 0.0
            for idx, n in enumerate(level_nodes):
                n.pos_y = cursor
                cursor += n.height
                if idx < len(level_nodes) - 1:
                    cursor += padding
            new_max = cursor - padding
            new_center = (0.0 + new_max) / 2.0
            shift = orig_center - new_center
            for n in level_nodes:
                n.pos_y += shift
        logger.debug("Applied variable-height packing for horizontal layout levels.")
