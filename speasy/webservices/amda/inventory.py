"""Base inventory tree management
"""
from ...core import fix_name
import xml.etree.ElementTree as Et
from speasy.inventory.indexes import CatalogIndex, ParameterIndex, TimetableIndex, DatasetIndex, ComponentIndex, \
    SpeasyIndex
from speasy.inventory import flat_inventories


def to_xmlid(index_or_str) -> str:
    if type(index_or_str) is str:
        return index_or_str
    if type(index_or_str) is dict and "xmlid" in index_or_str:
        return index_or_str['xmlid']
    if hasattr(index_or_str, 'xmlid'):
        return index_or_str.xmlid
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")


class AmdaXMLParser:

    @staticmethod
    def fix_names(**kwargs):
        return {fix_name(key): value for key, value in kwargs.items()}

    @staticmethod
    def fix_xmlid(**kwargs):
        def clean(key):
            if '}id' in key and key.startswith('{'):
                return 'xmlid'
            return key

        return {clean(key): value for key, value in kwargs.items()}

    @staticmethod
    def index_ctor_args(node, name_key='xmlid', is_public=True):
        meta = AmdaXMLParser.fix_names(**AmdaXMLParser.fix_xmlid(**node.attrib))
        meta['is_public'] = is_public
        return {"name": meta.get('name', node.tag), "provider": "amda", "meta": meta}

    @staticmethod
    def make_any_node(parent, node, ctor, name_key='xmlid', is_public=True):
        new = ctor(**AmdaXMLParser.index_ctor_args(node, is_public=is_public))
        name = fix_name(new.__dict__.get(name_key, node.tag))
        parent.__dict__[name] = new
        return new

    @staticmethod
    def make_instrument_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, SpeasyIndex, name_key='name', is_public=is_public)

    @staticmethod
    def make_dataset_node(parent, node, is_public=True):
        ds = AmdaXMLParser.make_any_node(parent, node, DatasetIndex, is_public=is_public)
        flat_inventories.amda.datasets[ds.xmlid] = ds
        return ds

    @staticmethod
    def make_parameter_node(parent, node, is_public=True):
        param = AmdaXMLParser.make_any_node(parent, node, ParameterIndex, is_public=is_public)
        param.product = param.xmlid
        flat_inventories.amda.parameters[param.xmlid] = param
        return param

    @staticmethod
    def make_component_node(parent, node, is_public=True):
        component = AmdaXMLParser.make_any_node(parent, node, ComponentIndex, is_public=is_public)
        flat_inventories.amda.components[component.xmlid] = component
        return component

    @staticmethod
    def make_timetable_node(parent, node, is_public=True):
        tt = AmdaXMLParser.make_any_node(parent, node, TimetableIndex, name_key='name', is_public=is_public)
        flat_inventories.amda.timetables[tt.xmlid] = tt
        return tt

    @staticmethod
    def make_catalogue_node(parent, node, is_public=True):
        cat = AmdaXMLParser.make_any_node(parent, node, CatalogIndex, name_key='name', is_public=is_public)
        flat_inventories.amda.catalogs[cat.xmlid] = cat
        return cat

    @staticmethod
    def make_path_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, SpeasyIndex, name_key='name', is_public=is_public)

    @staticmethod
    def parse(xml, is_public=True):
        handlers = {
            'instrument': AmdaXMLParser.make_instrument_node,
            'dataset': AmdaXMLParser.make_dataset_node,
            'parameter': AmdaXMLParser.make_parameter_node,
            'component': AmdaXMLParser.make_component_node,
            'timeTable': AmdaXMLParser.make_timetable_node,
            'timetab': AmdaXMLParser.make_timetable_node,
            'catalog': AmdaXMLParser.make_catalogue_node,
            'param': AmdaXMLParser.make_parameter_node,
        }

        def _recursive_parser(parent, node, is_public):
            new = handlers.get(node.tag, AmdaXMLParser.make_path_node)(parent, node, is_public)
            for subnode in node:
                _recursive_parser(new, subnode, is_public)

        root = SpeasyIndex("root", "amda")
        if xml is not None:
            tree = Et.fromstring(xml)
            root = SpeasyIndex("root", "amda")
            _recursive_parser(root, tree, is_public=is_public)

        return root
