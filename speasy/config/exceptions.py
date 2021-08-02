"""
spease.config.exceptions
------------------------

Exception definitions.
"""

class UndefinedConfigEntry(Exception):
    """Configuration entry is not defined.
    """
    def __init__(self, key1, key2, default):
        self.key1=key1
        self.key2=key2
        self.default=default
    def __str__(self):
        return "{} - key1 = ({}), key2 = ({}), default = ({})".format(super().__str__(),\
                self.key1,self.key2,self.default)

