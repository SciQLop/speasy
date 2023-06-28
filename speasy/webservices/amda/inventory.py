"""Base inventory tree management
"""
import xml.etree.ElementTree as Et

from ...core import fix_name
from ...core.inventory.indexes import (CatalogIndex, ComponentIndex,
                                       DatasetIndex, ParameterIndex,
                                       SpeasyIndex, TimetableIndex)
from ...inventories import flat_inventories


def to_xmlid(index_or_str) -> str:
    if type(index_or_str) is str:
        return index_or_str
    if type(index_or_str) is dict and "xmlid" in index_or_str:
        return index_or_str['xmlid']
    if hasattr(index_or_str, 'xmlid'):
        return index_or_str.xmlid
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")


def to_parameter_index(index_or_str) -> ParameterIndex:
    if type(index_or_str) is str:
        if index_or_str in flat_inventories.amda.parameters:
            return flat_inventories.amda.parameters[index_or_str]
        else:
            raise ValueError(f"Unknown parameter: {index_or_str}")

    if isinstance(index_or_str, ParameterIndex):
        return index_or_str
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")


def to_dataset_index(index_or_str) -> DatasetIndex:
    if type(index_or_str) is str:
        if index_or_str in flat_inventories.amda.datasets:
            return flat_inventories.amda.datasets[index_or_str]
        else:
            raise ValueError(f"Unknown dataset: {index_or_str}")

    if isinstance(index_or_str, DatasetIndex):
        return index_or_str
    else:
        raise TypeError(f"given dataset {index_or_str} of type {type(index_or_str)} is not a compatible index")


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
    def index_ctor_args(node, name_key='xmlid', is_public='True'):
        meta = AmdaXMLParser.fix_names(**AmdaXMLParser.fix_xmlid(**node.attrib))
        meta['is_public'] = is_public
        if 'dataStart' in meta:
            meta['start_date'] = meta.pop('dataStart')
        if 'dataStop' in meta:
            meta['stop_date'] = meta.pop('dataStop')
        uid = meta.get('xmlid', node.tag)
        return {"name": meta.get('name', node.tag), "provider": "amda", 'uid': uid, "meta": meta}

    @staticmethod
    def make_any_node(parent, node, ctor, name_key='xmlid', is_public='True'):
        new = ctor(**AmdaXMLParser.index_ctor_args(node, is_public=str(is_public)))
        name = fix_name(new.__dict__.get(name_key, node.tag))
        parent.__dict__[name] = new
        return new

    @staticmethod
    def make_instrument_node(parent, node, is_public=True):
        return AmdaXMLParser.make_any_node(parent, node, SpeasyIndex, name_key='name', is_public=is_public)

    @staticmethod
    def make_dataset_node(parent, node, is_public=True):
        ds = AmdaXMLParser.make_any_node(parent, node, DatasetIndex, is_public=is_public)
        return ds

    @staticmethod
    def make_parameter_node(parent, node, is_public=True):
        param = AmdaXMLParser.make_any_node(parent, node, ParameterIndex, is_public=is_public)
        if isinstance(parent, DatasetIndex):
            param.start_date = parent.start_date
            param.stop_date = parent.stop_date
            param.dataset = parent.spz_uid()
        return param

    @staticmethod
    def make_user_parameter_node(parent, node, is_public=True):
        # It seems that AMDA prevents users from using incompatible names here
        param = AmdaXMLParser.make_any_node(parent, node, ParameterIndex, name_key='name', is_public=is_public)
        return param

    @staticmethod
    def make_component_node(parent, node, is_public=True):
        component = AmdaXMLParser.make_any_node(parent, node, ComponentIndex, is_public=is_public)
        if isinstance(parent, ParameterIndex):
            component.start_date = parent.start_date
            component.stop_date = parent.stop_date
            component.dataset = parent.dataset
            component.parameter = parent.spz_uid()
        return component

    @staticmethod
    def make_timetable_node(parent, node, is_public=True):
        tt = AmdaXMLParser.make_any_node(parent, node, TimetableIndex, name_key='name', is_public=is_public)
        return tt

    @staticmethod
    def make_catalogue_node(parent, node, is_public=True):
        cat = AmdaXMLParser.make_any_node(parent, node, CatalogIndex, name_key='name', is_public=is_public)
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
            'param': AmdaXMLParser.make_user_parameter_node,
        }

        def _recursive_parser(parent, node, is_public):
            new = handlers.get(node.tag, AmdaXMLParser.make_path_node)(parent, node, is_public)
            for subnode in node:
                _recursive_parser(new, subnode, is_public)

        root = SpeasyIndex("root", "amda", "amda_root_node")
        if xml is not None:
            tree = Et.fromstring(xml)
            _recursive_parser(root, tree, is_public=is_public)

        return root
