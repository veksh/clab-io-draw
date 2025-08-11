import json
import logging
import os

import yaml as pyyaml

logger = logging.getLogger(__name__)


class GrafanaDashboard:
    """
    Manages the creation of a Grafana dashboard and associated panel config from the diagram data.
    """

    def __init__(self, diagram=None, grafana_config_path: str | None = None):
        """
        :param diagram: Diagram object that includes node and link data.
        :param grafana_config_path: Path to the YAML file containing grafana panel config (targets, thresholds, etc.).
        """
        self.diagram = diagram
        self.links = diagram.get_links_from_nodes() if diagram else []
        # The file where the final JSON will be saved
        self.dashboard_filename = (
            diagram.grafana_dashboard_file if diagram else "network_telemetry.json"
        )

        # Determine config path (default or user-provided)
        base_dir_env = os.getenv("APP_BASE_DIR")
        if grafana_config_path is None:
            if base_dir_env:
                # default location when running inside container or with APP_BASE_DIR
                grafana_config_path = os.path.join(
                    base_dir_env,
                    "core/grafana/config/default_grafana_panel_config.yml",
                )
            else:
                # default relative to this file when running from source tree
                grafana_config_path = os.path.join(
                    os.path.dirname(__file__),
                    "config",
                    "default_grafana_panel_config.yml",
                )

        self.grafana_config = self._load_grafana_config(grafana_config_path)

    def _load_grafana_config(self, path: str) -> dict:
        """
        Load the Grafana panel config from a YAML file.

        :param path: Path to the YAML config.
        :return: A dict with 'targets', 'thresholds', 'label_config'.
        """
        logger.debug("Loading Grafana config from: %s", path)
        if not os.path.exists(path):
            logger.error("Grafana config file not found: %s", path)
            raise FileNotFoundError(f"Grafana config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            config = pyyaml.safe_load(f)

        required_keys = ["targets", "thresholds", "label_config"]
        for key in required_keys:
            if key not in config:
                logger.warning(
                    "Missing key '%s' in Grafana config '%s'. Please verify the YAML structure.",
                    key,
                    path,
                )
                if key == "targets":
                    config["targets"] = []
                elif key == "thresholds":
                    config["thresholds"] = {"operstate": [], "traffic": []}
                elif key == "label_config":
                    config["label_config"] = {}

        return config

    def create_dashboard(self, panel_config: str) -> str:
        """
        Create a Grafana dashboard JSON string by loading a base template (flow_panel_template.json)
        and updating the panel with new targets from the config, plus embedding the panel_config.

        :param panel_config: YAML panel configuration as a string (the result of create_panel_yaml()).
        :return: The final dashboard as a JSON string.
        """
        logger.debug("Creating Grafana dashboard JSON from template...")

        base_dir_env = os.getenv("APP_BASE_DIR")
        if base_dir_env:
            template_path = os.path.join(
                base_dir_env, "core/grafana/templates/flow_panel_template.json"
            )
        else:
            template_path = os.path.join(
                os.path.dirname(__file__), "templates", "flow_panel_template.json"
            )
        if not os.path.exists(template_path):
            logger.error("Template not found at %s", template_path)
            raise FileNotFoundError(
                f"Grafana template file not found at {template_path}"
            )

        with open(template_path, encoding="utf-8") as file:
            dashboard_json = json.load(file)

        # Update the first panel’s 'targets' from the config
        if "panels" in dashboard_json and len(dashboard_json["panels"]) > 0:
            panel = dashboard_json["panels"][0]

            new_targets = []
            for i, tgt in enumerate(self.grafana_config["targets"]):
                # build target object as per template structure
                datasource_type = tgt.get("datasource", "prometheus")
                expr = tgt.get("expr", "")
                legend_format = tgt.get("legend_format", "")
                new_targets.append(
                    {
                        "datasource": {"type": datasource_type},
                        "editorMode": "code",
                        "expr": expr,
                        "hide": tgt.get("hide", False),
                        "instant": tgt.get("instant", False),
                        "legendFormat": legend_format,
                        "range": tgt.get("range", True),
                        # assign refId A, B, C,... automatically
                        "refId": chr(ord("A") + i),
                    }
                )

            panel["targets"] = new_targets

            # Also inject the newly built panel_yaml into `panelConfig`
            if "options" in panel:
                panel["options"]["panelConfig"] = panel_config
                # NOTE: siteConfig support (if needed) can be added similarly by setting panel["options"]["siteConfig"]

        dashboard_str = json.dumps(dashboard_json, indent=2)
        logger.debug("Grafana dashboard JSON created successfully.")
        return dashboard_str

    def create_panel_yaml(self) -> str:
        """
        Create the flow panel YAML configuration, pulling threshold info, label config, etc.
        from the loaded grafana config, plus adding link data.

        :return: String of the final YAML panel configuration.
        """
        logger.debug("Creating panel YAML from links and grafana config...")

        from ruamel.yaml import YAML, CommentedMap, CommentedSeq

        ryaml = YAML()
        ryaml.explicit_start = True
        ryaml.width = 4096

        root = CommentedMap()

        # Thresholds from config
        thresholds_operstate_config = self.grafana_config["thresholds"].get(
            "operstate", []
        )
        thresholds_traffic_config = self.grafana_config["thresholds"].get("traffic", [])
        devstate_config = self.grafana_config["thresholds"].get("devstate", [])
        label_cfg = self.grafana_config["label_config"]
        # New: Hyperlink configuration (simple: url, sameTab)
        hyperlink_cfg = self.grafana_config.get("hyperlink_config", {}) or {}

        # Collect all traffic-* thresholds
        traffic_thresholds = {"traffic": thresholds_traffic_config}
        for k, v in self.grafana_config["thresholds"].items():
            if k.startswith("traffic-"):
                traffic_thresholds[k] = v

        # Build the oper-state thresholds
        thresholds_operstate = CommentedSeq()
        for item in thresholds_operstate_config:
            thresholds_operstate.append(
                {"color": item["color"], "level": item["level"]}
            )
        thresholds_operstate.yaml_set_anchor("thresholds-operstate", always_dump=True)

        # Build devstate thresholds
        thresholds_devstate = CommentedSeq()
        for item in devstate_config:
            thresholds_devstate.append({"color": item["color"], "level": item["level"]})
        thresholds_devstate.yaml_set_anchor("thresholds-devstate", always_dump=True)

        # Build all traffic thresholds and anchors
        thresholds_traffic_anchors = {}
        for k, v in traffic_thresholds.items():
            seq = CommentedSeq()
            for item in v:
                seq.append({"color": item["color"], "level": item["level"]})
            anchor_name = "thresholds-" + k.replace("_", "-")
            seq.yaml_set_anchor(anchor_name, always_dump=True)
            thresholds_traffic_anchors[k] = seq
        # Default anchor reference kept via thresholds_traffic_anchors['traffic'] when needed

        label_config_map = CommentedMap()
        label_config_map["separator"] = label_cfg.get("separator", "replace")
        label_config_map["units"] = label_cfg.get("units", "bps")
        label_config_map["decimalPoints"] = label_cfg.get("decimalPoints", 1)
        label_config_map["valueMappings"] = label_cfg.get("valueMappings", [])
        label_config_map.yaml_set_anchor("label-config", always_dump=True)

        root["anchors"] = anchors = CommentedMap()
        anchors["thresholds-operstate"] = thresholds_operstate
        anchors["thresholds-devstate"] = thresholds_devstate
        for k, v in thresholds_traffic_anchors.items():
            anchors["thresholds-" + k.replace("_", "-")] = v
        anchors["label-config"] = label_config_map

        # Create and register hyperlink anchor if provided
        link_anchor_map = None
        if isinstance(hyperlink_cfg, dict) and hyperlink_cfg:
            link_anchor_map = CommentedMap()
            if "url" in hyperlink_cfg:
                link_anchor_map["url"] = hyperlink_cfg.get("url")
            if "sameTab" in hyperlink_cfg:
                link_anchor_map["sameTab"] = hyperlink_cfg.get("sameTab")
            if "params" in hyperlink_cfg:
                link_anchor_map["params"] = hyperlink_cfg.get("params")
            # Name the anchor 'dev-details'
            link_anchor_map.yaml_set_anchor("dev-details", always_dump=True)
            anchors["dev-details"] = link_anchor_map

        root["cellIdPreamble"] = "cell-"
        root["gradientMode"] = label_cfg.get("gradientMode", "none")

        cells = CommentedMap()
        root["cells"] = cells

        # Add node state (alerts) cells first
        if self.diagram and hasattr(self.diagram, 'nodes') and isinstance(self.diagram.nodes, dict):
            for node in self.diagram.nodes.values():
                metric_host = None
                if hasattr(node, 'labels') and node.labels:
                    metric_host = node.labels.get('metric-host')
                dataref_source = metric_host if metric_host else node.name
                # Use node.name directly so it matches Draw.io object id
                cell_id_node = node.name
                cell_node = CommentedMap()
                cell_node["dataRef"] = f"num_alerts:{dataref_source}"
                labelColor = CommentedMap()
                labelColor["thresholds"] = thresholds_devstate
                cell_node["strokeColor"] = labelColor
                # Attach hyperlink via anchor for node cells only
                if link_anchor_map is not None:
                    cell_node["link"] = link_anchor_map
                cells[cell_id_node] = cell_node

        # Add link data
        for link in self.links:
            source_name = link.source.name
            source_intf = link.source_intf
            target_name = link.target.name
            target_intf = link.target_intf

            metric_host = None
            if hasattr(link.source, 'labels') and link.source.labels:
                metric_host = link.source.labels.get('metric-host')
            dataref_source = metric_host if metric_host else source_name

            cell_id_operstate = f"{source_name}:{source_intf}:{target_name}:{target_intf}"
            dataRef_operstate = f"oper-state:{dataref_source}:{source_intf}"
            fillColor_operstate = CommentedMap()
            fillColor_operstate["thresholds"] = thresholds_operstate

            cell_operstate = CommentedMap()
            cell_operstate["dataRef"] = dataRef_operstate
            cell_operstate["fillColor"] = fillColor_operstate
            cells[cell_id_operstate] = cell_operstate

            cell_id_traffic = f"link_id:{source_name}:{source_intf}:{target_name}:{target_intf}"
            dataRef_traffic = f"{dataref_source}:{source_intf}:out"

            link_speed = None
            logger.debug("Processing link: %s", link)
            logger.debug("Link labels: %s", getattr(link, 'labels', None))
            logger.debug("Link source: %s, labels: %s", link.source, getattr(link.source, 'labels', None))
            logger.debug("Link target: %s, labels: %s", link.target, getattr(link.target, 'labels', None))

            if hasattr(link, 'labels') and isinstance(link.labels, dict):
                link_speed = link.labels.get('link-speed')
                logger.debug("Found link-level speed: %s", link_speed)
            if link_speed is None and hasattr(link.source, 'labels') and isinstance(link.source.labels, dict):
                link_speed = link.source.labels.get('link-speed')
                logger.debug("Found source node speed: %s", link_speed)
            if link_speed is None and hasattr(link.target, 'labels') and isinstance(link.target.labels, dict):
                link_speed = link.target.labels.get('link-speed')
                logger.debug("Found target node speed: %s", link_speed)

            anchor_key = "traffic"
            if link_speed is not None:
                speed_key = str(link_speed).strip().upper()
                anchor_candidate = f"traffic-{speed_key}"
                anchor_map = {k.upper(): k for k in thresholds_traffic_anchors.keys()}
                if anchor_candidate.upper() in anchor_map:
                    anchor_key = anchor_map[anchor_candidate.upper()]
                    logger.debug("Using %s threshold for link with speed %s", anchor_key, link_speed)
                else:
                    logger.warning("No threshold found for link speed %s, using default traffic threshold", link_speed)

            strokeColor_traffic = CommentedMap()
            strokeColor_traffic["thresholds"] = thresholds_traffic_anchors[anchor_key]

            cell_traffic = CommentedMap()
            cell_traffic["dataRef"] = dataRef_traffic
            cell_traffic["label"] = label_config_map
            cell_traffic["strokeColor"] = strokeColor_traffic
            cells[cell_id_traffic] = cell_traffic

        import io
        stream = io.StringIO()
        ryaml.dump(root, stream)
        panel_yaml = stream.getvalue()
        logger.debug("Panel YAML created successfully.")
        return panel_yaml
