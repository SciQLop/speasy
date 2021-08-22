"""Base inventory tree management
"""
from typing import Dict, Sequence
from types import SimpleNamespace
from ...core import listify
from .indexes import AMDATimetableIndex, AMDAComponentIndex, AMDAParameterIndex, AMDADatasetIndex, AMDACatalogIndex
import xml.etree.ElementTree as Et


class AMDAPathIndex(SimpleNamespace):
    def __init__(self, meta, is_public=True):
        super().__init__(**meta, is_public=is_public)


class AmdaXMLParser:
    @staticmethod
    def fix_name(name: str):
        return name.strip().replace('-', '_').replace(':', '').replace('.', '_').replace('(', '').replace(')',
                                                                                                          '').replace(
            '/', '').replace(' ', '')

    @staticmethod
    def fix_names(**kwargs):
        return {AmdaXMLParser.fix_name(key): value for key, value in kwargs.items()}

    @staticmethod
    def fix_xmlid(**kwargs):
        def clean(key):
            if '}id' in key and key.startswith('{'):
                return 'xmlid'
            return key

        return {clean(key): value for key, value in kwargs.items()}

    @staticmethod
    def make_any_node(parent, node, ctor, name_key='xmlid', is_public=True):
        new = ctor(AmdaXMLParser.fix_names(**AmdaXMLParser.fix_xmlid(**node.attrib)), is_public=is_public)
        name = AmdaXMLParser.fix_name(new.__dict__.get(name_key, node.tag))
        parent.__dict__[name] = new
        return new

    @staticmethod
    def make_instrument_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, AMDAPathIndex, name_key='name', is_public=is_public)

    @staticmethod
    def make_dataset_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, AMDADatasetIndex, is_public=is_public)

    @staticmethod
    def make_parameter_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, AMDAParameterIndex, is_public=is_public)

    @staticmethod
    def make_component_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, AMDAComponentIndex, is_public=is_public)

    @staticmethod
    def make_timetable_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, AMDATimetableIndex, name_key='name', is_public=is_public)

    @staticmethod
    def make_catalogue_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, AMDACatalogIndex, name_key='name', is_public=is_public)

    @staticmethod
    def make_path_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, AMDAPathIndex, name_key='name', is_public=is_public)

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

        if xml is not None:
            tree = Et.fromstring(xml)
            root = SimpleNamespace()
            _recursive_parser(root, tree, is_public=is_public)
            return root
        else:
            return SimpleNamespace()
