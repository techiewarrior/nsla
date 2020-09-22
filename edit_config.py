#!/usr/bin/env python

"""
Author: Nick Russo
Purpose: Demonstrate NETCONF on IOS-XE and IOS-XR coupled
with Nornir to update VRF route-target configurations.
"""

from nornir import InitNornir
import json
import xmltodict
from ncclient import manager
from lxml.etree import fromstring


def configure_probes(task, xml_config):

    conn = task.host.get_connection("netconf", task.nornir.config)

    print(f"{task.host.name}: Connection open")

    breakpoint()
    config_resp = conn.edit_config(
        target="candidate",
        config=xml_config,
    )
    
    # Perform validation everywhere to gain network-wide
    # atomicity as best as we can
    validate = conn.validate()
    if not validate.ok:
        print(validate.xml)

    # Copy from candidate to running config
    commit = conn.commit()
    if not commit.ok:
        print(commit.xml)

    # Copy from running to startup config
    save = save_config_ios(conn)
    if not save.ok:
        print(save.xml)


def main():
    """
    Execution begins here.
    """

    # Initialize Nornir and run the manage_config custom task
    nornir = InitNornir()

    entry_list = []
    schedule_list = []
    for host, v in nornir.inventory.hosts.items():
        print(f"Building SLA entry for {host}")
        entry = build_sla_entry(v)
        entry_list.append(entry)

        schedule = build_sla_schedule(v)
        schedule_list.append(schedule)

    #print(entry_list)
    #print(schedule_list)

    wrapper = {
        "config": {
            "native": {
                "@xmlns": "http://cisco.com/ns/yang/Cisco-IOS-XE-native",
                "ip": {
                    "sla": {
                        "@xmlns": "http://cisco.com/ns/yang/Cisco-IOS-XE-sla",
                        "@operation": "replace",
                        "responder": None,
                        "entry": entry_list,
                        "schedule": schedule_list
                    }
                }
            }
        }
    }
    xml_config = xmltodict.unparse(wrapper, pretty=True)

    print("Generic config completed")
    print(xml_config)
    result = nornir.run(task=configure_probes, xml_config=xml_config)
    breakpoint()
    print(result)


def build_sla_entry(v):
    return {
        "number": v["node_id"],
        "udp-jitter": {
            "dest-addr": v["ipsla_addr"],
            "portno": v["destination_port"],
            "num-packets": v["packet_count"],
            "interval": v["packet_interval_ms"],
            #"source-ip": None, TODO
            "frequency": v["frequency_s"],
            "timeout": v["timeout_ms"],
            "tos": v["tos"],
            "verify-data": "true"
        }
    }

def build_sla_schedule(v):
    return {
        "entry-number": v["node_id"],
        "life": "forever",
        "start-time": {
            "now-config": None,
            "now": None
        }
    }


def save_config_ios(conn):
    """
    Save config on Cisco XE is complex due to presence of startup-config.
    Need to use custom RPC string formed into XML document to save.
    """
    save_rpc = '<save-config xmlns="http://cisco.com/yang/cisco-ia"/>'
    save_resp = conn.dispatch(fromstring(save_rpc))

    # Return the RPC response
    return save_resp


if __name__ == "__main__":
    main()