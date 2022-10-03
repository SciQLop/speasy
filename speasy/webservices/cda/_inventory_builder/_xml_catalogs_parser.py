from speasy.core import fix_name
from speasy.core.inventory.indexes import DatasetIndex, SpeasyIndex, make_inventory_node
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


def extract_node(node, is_dataset=False):
    name = node.attrib["serviceprovider_ID"]
    n = {
        'name': fix_name(alias_rules(name)),
        'description': description(node)
    }
    n.update(node.attrib)
    if is_dataset:
        n['start_date'] = n.pop('timerange_start')
        n['stop_date'] = n.pop('timerange_stop')
        master_cd_node = node.find('{cdas}mastercdf')
        if master_cd_node is not None:
            n["mastercdf"] = master_cd_node.attrib["serviceprovider_ID"]
    return n


def register_dataset(inventory_tree, mission_group_node, observatory_node, instrument_node, dataset_node):
    observatory = extract_node(observatory_node)
    mission_group = extract_node(mission_group_node)
    if mission_group['name'] != observatory['name']:
        inventory_tree = make_inventory_node(inventory_tree, SpeasyIndex, provider="cda",
                                             uid=mission_group.get('serviceprovider_ID'), **mission_group)
    inventory_tree = make_inventory_node(inventory_tree, SpeasyIndex, provider="cda",
                                         uid=observatory.get('serviceprovider_ID'), **observatory)
    if instrument_node.attrib["serviceprovider_ID"] != "":
        inventory_tree = make_inventory_node(inventory_tree, SpeasyIndex, provider="cda",
                                             uid=instrument_node.get('serviceprovider_ID'), **extract_node(instrument_node))
    inventory_tree = make_inventory_node(inventory_tree, DatasetIndex, provider="cda",
                                         uid=dataset_node.get('serviceprovider_ID'),
                                         **extract_node(dataset_node, is_dataset=True))
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


def load_xml_catalog(xml_file_path: str, root: SpeasyIndex or None = None):
    with open(xml_file_path) as xml_file:
        tree = Et.fromstring(xml_file.read())
        inventory_tree = root or SpeasyIndex(name='root', provider='cda', uid='cda_root')
        for site in tree.iter('{cdas}datasite'):
            if site.attrib['ID'] == 'CDAWeb_HTTPS':
                for node in site.iter('{cdas}dataset'):
                    parse_dataset(inventory_tree, node)
        return inventory_tree
