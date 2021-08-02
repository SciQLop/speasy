"""Class for storing the time-table tree
"""
from ..common import listify

class TimeTableNode:
    def __init__(self, node):
        self.node=node
    @staticmethod
    def from_node(node):
        return TimeTableNode(node)
    def __str__(self):
        return "TimeTableNode (id:{}, name:{})".format(self["id"], self["name"])
    def __getitem__(self, i):
        return self.node.attrib[i]
    def __setitem__(self, i, v):
        if not i in self.node.attrib:
            return
        self.node.attrib[i]=v

class TimeTableTree:
    def __init__(self, tree):
        self.tree = tree
    def iter_timetable(self):
        for e in self.tree.iter(tag="timeTable"):
            yield TimeTableNode.from_node(e)
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
                    value[name] = TimeTableTree.node_to_dict(subnode, **kwargs)
                    TimeTableTree.enter_nodes(subnode, storage=storage, **kwargs)

    @staticmethod
    def extrac_all(tree, storage):
        TimeTableTree.enter_nodes(tree['timeTableList'], storage)


