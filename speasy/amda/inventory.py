"""Base inventory tree management
"""
from ..common import listify

class InventoryTree:
    @staticmethod
    def node_to_dict(node, **kwargs):
        """Convert node of the timetable tree to dictionary

        :param node: tree node
        :type node: ??
        :return: node as dictionary
        :rtype: dict
        """
        d = {key.replace('@', ''): value for key, value in node.items() if type(value) is str}
        d.update(kwargs)
        return d

    @staticmethod
    def enter_nodes(node, storage, **kwargs):
        for key, value in storage.items():
            if key in node:
                for subnode in listify(node[key]):
                    name = subnode['@xml:id']
                    kwargs[key] = name
                    value[name] = InventoryTree.node_to_dict(subnode, **kwargs)
                    InventoryTree.enter_nodes(subnode, storage=storage, **kwargs)

    @staticmethod
    def extrac_all(tree, storage):
        InventoryTree.enter_nodes(tree, storage)


