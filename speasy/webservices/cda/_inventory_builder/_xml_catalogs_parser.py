from types import SimpleNamespace
from speasy.webservices.cda.indexes import CDAComponentIndex, CDADatasetIndex, CDAParameterIndex, CDAPathIndex
from ._cdf_masters_parser import load_master_cdf
from speasy.core import fix_name
import xml.etree.ElementTree as Et


def alias_rules(name):
    rules = {
        "AC": "ACE",
        "Parker Solar Probe (PSP)": "ParkerSolarProbe",
        "PSP": "ParkerSolarProbe",
        "mms1": "MMS1",
        "mms2": "MMS2",
        "mms3": "MMS3",
        "mms4": "MMS4",
    }
    return rules.get(name, name)


def description(node) -> str:
    desc_node = node.find('{cdas}description')
    if desc_node is not None:
        return desc_node.attrib['short']
    return ""


def make_inventory_node(inventory_node, ctor, name, *args, **kwargs):
    if name not in inventory_node.__dict__:
        inventory_node.__dict__[name] = ctor(name=name, *args, **kwargs)
    return inventory_node.__dict__[name]


def extract_node(node, is_dataset=False):
    name = node.attrib["serviceprovider_ID"]
    n = {
        'name': fix_name(alias_rules(name)),
        'description': description(node)
    }
    if is_dataset:
        master_cd_node = node.find('{cdas}mastercdf')
        if master_cd_node is not None:
            n["mastercdf"] = master_cd_node.attrib["serviceprovider_ID"]
    n.update(node.attrib)
    return n


def register_dataset(inventory_tree, mission_group_node, observatory_node, instrument_node, dataset_node):
    observatory = extract_node(observatory_node)
    mission_group = extract_node(mission_group_node)
    if mission_group['name'] != observatory['name']:
        inventory_tree = make_inventory_node(inventory_tree, CDAPathIndex, **mission_group)
    inventory_tree = make_inventory_node(inventory_tree, CDAPathIndex, **observatory)
    inventory_tree = make_inventory_node(inventory_tree, CDAPathIndex, **extract_node(instrument_node))
    inventory_tree = make_inventory_node(inventory_tree, CDADatasetIndex, **extract_node(dataset_node, is_dataset=True))
    return inventory_tree


def has_master_cdf(node):
    master_cdf = node.find('{cdas}mastercdf')
    if master_cdf is not None:
        return True
    return None


def parse_dataset(inventory_tree, dataset_node):
    mission_group_node = dataset_node.find('{cdas}mission_group')
    observatory_node = dataset_node.find('{cdas}observatory')
    instrument_node = dataset_node.find('{cdas}instrument')
    if has_master_cdf(dataset_node):
        return register_dataset(inventory_tree, mission_group_node, observatory_node, instrument_node, dataset_node)
    else:
        print(f'Missing master CDF for {dataset_node.attrib["serviceprovider_ID"]}')


def load_xml_catalog(xml_file_path: str):
    with open(xml_file_path) as xml_file:
        tree = Et.fromstring(xml_file.read())
        inventory_tree = SimpleNamespace()
        for site in tree.iter('{cdas}datasite'):
            if site.attrib['ID'] == 'CDAWeb_HTTPS':
                for node in site.iter('{cdas}dataset'):
                    parse_dataset(inventory_tree, node)
                return inventory_tree

