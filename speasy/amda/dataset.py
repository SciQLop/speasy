"""AMDA Dataset definition. In AMDA datasets are collections of Parameter objects with the same time
base.
"""

class Dataset:
    """AMDA Dataset container.

    :param parameters: dictionary containing parameters
    :type parameters: dict
    """
    def __init__(self, parameters={}):
        """Constructor
        """
        self.parameters=parameters
    def __len__(self):
        return len(self.parameters)
    
