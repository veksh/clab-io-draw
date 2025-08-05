import json
import logging
import os

import yaml

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
        logger.debug(f"Loading Grafana config from: {path}")
        if not os.path.exists(path):
            logger.error(f"Grafana config file not found: {path}")
            raise FileNotFoundError(f"Grafana config file not found: {path}")

        with open(path) as f:
            config = yaml.safe_load(f)

        required_keys = ["targets", "thresholds", "label_config"]
        for key in required_keys:
            if key not in config:
                logger.warning(
                    f"Missing key '{key}' in Grafana config '{path}'. Please verify the YAML structure."
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
            logger.error(f"Template not found at {template_path}")
            raise FileNotFoundError(
                f"Grafana template file not found at {template_path}"
            )

        with open(template_path) as file:
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

        yaml = YAML()
        yaml.explicit_start = True
        yaml.width = 4096

        root = CommentedMap()

        # Thresholds from config
        thresholds_operstate_config = self.grafana_config["thresholds"].get(
            "operstate", []
        )
        thresholds_traffic_config = self.grafana_config["thresholds"].get("traffic", [])
        label_cfg = self.grafana_config["label_config"]

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

        # Build all traffic thresholds and anchors
        thresholds_traffic_anchors = {}
        for k, v in traffic_thresholds.items():
            seq = CommentedSeq()
            for item in v:
                seq.append({"color": item["color"], "level": item["level"]})
            anchor_name = "thresholds-" + k.replace("_", "-")
            seq.yaml_set_anchor(anchor_name, always_dump=True)
            thresholds_traffic_anchors[k] = seq
        # Default traffic anchor
        thresholds_traffic = thresholds_traffic_anchors["traffic"]

        label_config_map = CommentedMap()
        label_config_map["separator"] = label_cfg.get("separator", "replace")
        label_config_map["units"] = label_cfg.get("units", "bps")
        label_config_map["decimalPoints"] = label_cfg.get("decimalPoints", 1)
        label_config_map["valueMappings"] = label_cfg.get("valueMappings", [])
        label_config_map.yaml_set_anchor("label-config", always_dump=True)

        root["anchors"] = anchors = CommentedMap()
        anchors["thresholds-operstate"] = thresholds_operstate
        for k, v in thresholds_traffic_anchors.items():
            anchors["thresholds-" + k.replace("_", "-")] = v
        anchors["label-config"] = label_config_map

        root["cellIdPreamble"] = "cell-"
        cells = CommentedMap()
        root["cells"] = cells

        # Add link data
        for link in self.links:
            source_name = link.source.name
            source_intf = link.source_intf
            target_name = link.target.name
            target_intf = link.target_intf

            # Use metric-host label for dataRef if present, with prefix
            metric_host = None
            if hasattr(link.source, 'labels') and link.source.labels:
                metric_host = link.source.labels.get('metric-host')
            # Extract lab_name from source_name (assumes format: prefix-labname-nodename)
            lab_prefix = ''
            if '-' in source_name:
                parts = source_name.split('-')
                if len(parts) >= 3:
                    lab_prefix = '-'.join(parts[:2])  # e.g. clab-coxgs
            if metric_host:
                # Remove any existing prefix from metric_host, then prepend lab_prefix
                metric_host_base = metric_host
                if metric_host.startswith(lab_prefix + '-'):
                    metric_host_base = metric_host[len(lab_prefix)+1:]
                dataref_source = f"{lab_prefix}-{metric_host_base}" if lab_prefix else metric_host
            else:
                dataref_source = source_name

            # oper-state cell
            cell_id_operstate = (
                f"{source_name}:{source_intf}:{target_name}:{target_intf}"
            )
            dataRef_operstate = f"oper-state:{dataref_source}:{source_intf}"
            fillColor_operstate = CommentedMap()
            fillColor_operstate["thresholds"] = thresholds_operstate

            cell_operstate = CommentedMap()
            cell_operstate["dataRef"] = dataRef_operstate
            cell_operstate["fillColor"] = fillColor_operstate
            cells[cell_id_operstate] = cell_operstate

            # traffic cell
            cell_id_traffic = (
                f"link_id:{source_name}:{source_intf}:{target_name}:{target_intf}"
            )
            dataRef_traffic = f"{dataref_source}:{source_intf}:out"

            # Determine link-speed for threshold selection
            link_speed = None
            # Debug the link object structure
            logger.debug(f"Processing link: {link}")
            logger.debug(f"Link labels: {getattr(link, 'labels', None)}")
            logger.debug(f"Link source: {link.source}, labels: {getattr(link.source, 'labels', None)}")
            logger.debug(f"Link target: {link.target}, labels: {getattr(link.target, 'labels', None)}")

            # 1. Check link labels first - they have priority
            if hasattr(link, 'labels') and isinstance(link.labels, dict):
                # Direct label access, no .get() to see if key exists at all
                link_speed = link.labels.get('link-speed')
                logger.debug(f"Found link-level speed: {link_speed}")

            # 2. Only if no link-level speed defined, check nodes
            if link_speed is None:
                # Source node
                if hasattr(link.source, 'labels') and isinstance(link.source.labels, dict):
                    link_speed = link.source.labels.get('link-speed')
                    logger.debug(f"Found source node speed: {link_speed}")

                # Target node - only check if still no speed found
                if link_speed is None and hasattr(link.target, 'labels') and isinstance(link.target.labels, dict):
                    link_speed = link.target.labels.get('link-speed')
                    logger.debug(f"Found target node speed: {link_speed}")

            # 4. Normalize and build anchor name
            anchor_key = "traffic"
            if link_speed is not None:
                # Accept values like '1G', '10G', '100G', case-insensitive
                speed_key = str(link_speed).strip().upper()
                anchor_candidate = f"traffic-{speed_key}"
                # Case-insensitive lookup in available anchors
                anchor_map = {k.upper(): k for k in thresholds_traffic_anchors.keys()}
                if anchor_candidate.upper() in anchor_map:
                    anchor_key = anchor_map[anchor_candidate.upper()]
                    logger.debug(f"Using {anchor_key} threshold for link with speed {link_speed}")
                else:
                    logger.warning(f"No threshold found for link speed {link_speed}, using default traffic threshold")
            
            strokeColor_traffic = CommentedMap()
            strokeColor_traffic["thresholds"] = thresholds_traffic_anchors[anchor_key]

            cell_traffic = CommentedMap()
            cell_traffic["dataRef"] = dataRef_traffic
            cell_traffic["label"] = label_config_map
            cell_traffic["strokeColor"] = strokeColor_traffic
            cells[cell_id_traffic] = cell_traffic

        import io

        stream = io.StringIO()
        yaml.dump(root, stream)
        panel_yaml = stream.getvalue()
        logger.debug("Panel YAML created successfully.")
        return panel_yaml
