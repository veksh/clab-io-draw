#!/usr/bin/env python3
"""
netbox2clab - Extract network topology from Netbox and dump links in yaml format

Usage:
    python ./netbox2clab.py --url https://netbox.oxford --devices spine-coxgs-1,spine-coxgs-2

Install:

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

then run as ./venv/bin/python netbox2clab.py ...
"""

import argparse
import os
import sys
import yaml
from typing import List, Dict, Any, Set, Tuple
import pynetbox
from pynetbox.core.response import Record


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract network topology from Netbox and convert to containerlab YAML format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python ./netbox2clab.py --url https://netbox.oxford --devices spine-coxgs-1,spine-coxgs-2
or just
  python ./netbox2clab.py --devices spine-coxgs-1,spine-coxgs-2,etc

        """
    )

    parser.add_argument(
        '--url',
        required=False,
        default="https://netbox.oxford",
        help='Netbox URL (default: https://netbox.oxford)'
    )

    parser.add_argument(
        '--devices',
        required=True,
        help='Comma-separated list of device names, required'
    )

    parser.add_argument(
        '--verify-ssl',
        action='store_true',
        default=False,
        help='Verify SSL certificates (default: False)'
    )

    return parser.parse_args()

def connect_to_netbox(url: str, verify_ssl: bool = False) -> pynetbox.api:
    """Connect to Netbox API."""
    try:
        # Create a session with SSL verification settings
        import requests
        session = requests.Session()
        session.verify = verify_ssl

        # Connect to Netbox
        nb = pynetbox.api(url=url)
        nb.http_session = session

        # Test connection
        nb.status()
        return nb
    except Exception as e:
        print(f"Error connecting to Netbox at {url}: {e}")
        sys.exit(1)


def validate_devices(nb: pynetbox.api, device_names: List[str]) -> List[Record]:
    """Validate that all specified devices exist in Netbox."""
    devices = []
    missing_devices = []

    for device_name in device_names:
        try:
            device = nb.dcim.devices.get(name=device_name)
            if device:
                devices.append(device)
            else:
                missing_devices.append(device_name)
        except Exception as e:
            print(f"Error querying device '{device_name}': {e}")
            missing_devices.append(device_name)

    if missing_devices:
        print(f"Error: The following devices were not found in Netbox: {', '.join(missing_devices)}")
        sys.exit(1)

    return devices


def get_device_interfaces(nb: pynetbox.api, device: Record) -> List[Record]:
    """Get all interfaces for a device."""
    try:
        interfaces = list(nb.dcim.interfaces.filter(device=device.name))
        return interfaces
    except Exception as e:
        print(f"Error getting interfaces for device '{device.name}': {e}")
        return []


def get_connected_devices_and_interfaces(nb: pynetbox.api, devices: List[Record], 
                                       device_names: List[str]) -> List[Tuple[str, str, str, str]]:
    """
    Get all connections between the specified devices.
    Returns list of tuples: (device_a_name, interface_a_name, device_b_name, interface_b_name)
    """
    connections = []
    processed_cables = set()
    device_names_set = set(device_names)

    for device in devices:
        interfaces = get_device_interfaces(nb, device)

        for interface in interfaces:
            # Skip if interface has no cable
            if not interface.cable:
                continue

            # Skip if we've already processed this cable
            cable_id = interface.cable.id
            if cable_id in processed_cables:
                continue

            try:
                # Get the full cable object
                cable = nb.dcim.cables.get(cable_id)
                if not cable:
                    continue
                if not (hasattr(cable, 'a_terminations') and hasattr(cable, 'b_terminations')):
                    continue
                if not (len(cable.a_terminations) == 1 and len(cable.b_terminations) == 1):
                    continue

                ta = cable.a_terminations[0]
                tb = cable.b_terminations[0]

                if ta.device.name in device_names_set and tb.device.name in device_names_set:
                    if device_names.index(tb.device.name) < device_names.index(ta.device.name):
                        ta, tb = tb, ta
                    connections.append((
                        ta.device.name,
                        ta.name,
                        tb.device.name,
                        tb.name
                    ))

                processed_cables.add(cable_id)

            except Exception as e:
                print(f"Warning: Error processing cable {cable_id}: {e}")
                continue

    return connections


def format_interface_name(intf_name):
    # if intf_name.lower().startswith("ethernet-"):
    #     return "e" + intf_name[9:]
    # if intf_name.lower().startswith("ethernet"):
    #     return "e" + intf_name[8:]
    # if intf_name.startswith("Ethernet"):
    #     return "E" + intf_name[8:]
    if intf_name.startswith("TenGigabitEthernet"):
        return "Te" + intf_name[18:]
    return intf_name

def main():
    """Main application function."""
    args = parse_arguments()

    # Parse device list
    device_names = [name.strip() for name in args.devices.split(',')]

    print(f"Connecting to Netbox at {args.url}...")
    nb = connect_to_netbox(args.url, args.verify_ssl)

    print(f"Validating devices: {', '.join(device_names)}...")
    devices = validate_devices(nb, device_names)

    print("Discovering network connections...")
    connections = get_connected_devices_and_interfaces(nb, devices, device_names)

    print(f"Found {len(connections)} connections between specified devices\n\n")

    print(f"topology:")
    print(f"  links:")
    for a_device, a_interface, b_device, b_interface in sorted(connections,
            key=lambda c: (device_names.index(c[0]), device_names.index(c[2]), c[1])):
        src = f"'{a_device}:{format_interface_name(a_interface)}'"
        dst = f"'{b_device}:{format_interface_name(b_interface)}'"
        print(f"  - endpoints: [{src:<30}, {dst}]")

if __name__ == '__main__':
    main()
