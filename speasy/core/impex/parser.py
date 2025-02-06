"""Base inventory tree management
"""
import xml.etree.ElementTree as Et

from ...core import fix_name
from ...core.inventory.indexes import (CatalogIndex, ComponentIndex,
                                       DatasetIndex, ParameterIndex,
                                       ArgumentListIndex, ArgumentIndex,
                                       TemplatedParameterIndex, SpeasyIndex,
                                       TimetableIndex)


def to_xmlid(index_or_str) -> str:
    if type(index_or_str) is str:
        return index_or_str
    if type(index_or_str) is dict and "xmlid" in index_or_str:
        return index_or_str['xmlid']
    if hasattr(index_or_str, 'xmlid'):
        return index_or_str.xmlid
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")


class ImpexXMLParser:

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
    def index_ctor_args(node, provider_name, is_public: bool = True):
        meta = ImpexXMLParser.fix_names(**ImpexXMLParser.fix_xmlid(**node.attrib))
        meta['is_public'] = is_public
        if 'dataStart' in meta:
            meta['start_date'] = meta.pop('dataStart')
        if 'dataStop' in meta:
            meta['stop_date'] = meta.pop('dataStop')
        uid = meta.get('xmlid', node.tag)
        return {"name": meta.get('name', node.tag), "provider": provider_name, 'uid': uid, "meta": meta}

    @staticmethod
    def make_any_node(parent, node, provider_name, ctor, name_key='xmlid', is_public: bool = True):
        new = ctor(**ImpexXMLParser.index_ctor_args(node, provider_name, is_public=is_public))
        name = fix_name(new.__dict__.get(name_key, node.tag))
        parent.__dict__[name] = new
        return new

    @staticmethod
    def make_dataset_node(parent, node, provider_name, name_key, is_public: bool = True):
        ds = ImpexXMLParser.make_any_node(parent, node, provider_name, DatasetIndex, name_key=name_key,
                                          is_public=is_public)
        return ds

    @staticmethod
    def make_parameter_node(parent, node, provider_name, name_key, is_public: bool = True):
        if arguments:=node.find('.//arguments'):
            arguments.set('name', '__spz_arguments__')
            param = ImpexXMLParser.make_any_node(parent, node, provider_name, TemplatedParameterIndex, name_key=name_key,
                                                 is_public=is_public)
        else:
            param = ImpexXMLParser.make_any_node(parent, node, provider_name, ParameterIndex, name_key=name_key,
                                                 is_public=is_public)
        if isinstance(parent, DatasetIndex):
            param.start_date = parent.start_date
            param.stop_date = parent.stop_date
            param.dataset = parent.spz_uid()
        return param

    @staticmethod
    def make_user_parameter_node(parent, node, provider_name, name_key, is_public: bool = True):
        # It seems that AMDA prevents users from using incompatible names here
        param = ImpexXMLParser.make_any_node(parent, node, provider_name, ParameterIndex, name_key=name_key,
                                             is_public=is_public)
        return param

    @staticmethod
    def make_component_node(parent, node, provider_name, name_key, is_public: bool = True):
        component = ImpexXMLParser.make_any_node(parent, node, provider_name, ComponentIndex, name_key=name_key,
                                                 is_public=is_public)
        if isinstance(parent, ParameterIndex):
            component.start_date = parent.start_date
            component.stop_date = parent.stop_date
            component.dataset = parent.dataset
            component.parameter = parent.spz_uid()
        return component

    @staticmethod
    def make_timetable_node(parent, node, provider_name, name_key, is_public: bool = True):
        tt = ImpexXMLParser.make_any_node(parent, node, provider_name, TimetableIndex, name_key=name_key,
                                          is_public=is_public)
        return tt

    @staticmethod
    def make_catalog_node(parent, node, provider_name, name_key, is_public: bool = True):
        cat = ImpexXMLParser.make_any_node(parent, node, provider_name, CatalogIndex, name_key=name_key,
                                           is_public=is_public)
        return cat

    @staticmethod
    def make_path_node(parent, node, provider_name, name_key, is_public: bool = True):
        return ImpexXMLParser.make_any_node(parent, node, provider_name, SpeasyIndex, name_key=name_key,
                                            is_public=is_public)

    @staticmethod
    def parse_template_arguments(parent, node, provider_name, name_key, is_public: bool = True):
        return ImpexXMLParser.make_any_node(parent, node, provider_name, ArgumentListIndex, name_key=name_key,
                                            is_public=is_public)

    @staticmethod
    def parse_template_argument(parent, node, provider_name, name_key, is_public: bool = True):
        if node.get('type') == 'list':
            choices = []
            for item in node.findall('.//item'):
                choices.append((item.get('name'), item.get('key')))
                node.remove(item)
            node.set('choices', choices)
        elif node.get('type') == 'generated-list':
            node.set('type', 'list')
            choices = []
            for k in range(int(node.get('minkey')), int(node.get('maxkey'))):
                choices.append((node.get('nametpl').replace('##key##', str(k), 1), str(k)))
            node.set('choices', choices)

        return ImpexXMLParser.make_any_node(parent, node, provider_name, ArgumentIndex, name_key=name_key,
                                            is_public=is_public)


    @staticmethod
    def parse(xml, provider_name, name_mapping=None, is_public: bool = True):
        handlers = {
            'mission': ImpexXMLParser.make_path_node,
            'observatory': ImpexXMLParser.make_path_node,
            'datasetGroup': ImpexXMLParser.make_path_node,
            'instrument': ImpexXMLParser.make_path_node,
            'dataset': ImpexXMLParser.make_dataset_node,
            'parameter': ImpexXMLParser.make_parameter_node,
            'component': ImpexXMLParser.make_component_node,
            'timeTable': ImpexXMLParser.make_timetable_node,
            'timetab': ImpexXMLParser.make_timetable_node,
            'catalog': ImpexXMLParser.make_catalog_node,
            'param': ImpexXMLParser.make_user_parameter_node,
            'arguments': ImpexXMLParser.parse_template_arguments,
            'argument': ImpexXMLParser.parse_template_argument
        }

        def _recursive_parser(parent, node, is_node_public):
            if name_mapping and node.tag in name_mapping:
                name_key = name_mapping[node.tag]
            elif node.tag not in handlers.keys():
                name_key = ''
            else:
                name_key = 'name'
            new = handlers.get(node.tag, ImpexXMLParser.make_path_node)(parent, node, provider_name, name_key,
                                                                        is_node_public)
            for subnode in node:
                _recursive_parser(new, subnode, is_node_public)

        root = SpeasyIndex("root", provider_name, f"{provider_name}_root_node")
        if xml is not None:
            tree = Et.fromstring(xml)
            _recursive_parser(root, tree, is_node_public=is_public)

        return root
