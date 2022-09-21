from typing import Optional

from speasy.core import all_of_type
from speasy.core.datetime_range import DateTimeRange
from speasy.products.variable import SpeasyVariable

from .base_product import SpeasyProduct


class Dataset(SpeasyProduct):
    """A Dataset is basically a collection of SpeasyVariables

    """
    __slots__ = ['name', 'variables', 'meta']

    def __init__(self, name: str, variables: dict, meta: dict):
        super().__init__()
        if not all_of_type(variables.values(), SpeasyVariable):
            raise TypeError(f"variables must be a {dict} with {SpeasyVariable} as values")
        self.name = name
        self.variables = variables
        self.meta = meta

    def time_range(self) -> Optional[DateTimeRange]:
        start = min(map(lambda v: v.time[0], filter(len, self.variables.values())), default=None)
        stop = max(map(lambda v: v.time[-1], filter(len, self.variables.values())), default=None)
        if start and stop:
            return DateTimeRange(start, stop)
        return None

    def __len__(self):
        return len(self.variables)

    def __getitem__(self, variable_name):
        return self.variables[variable_name]

    def __repr__(self):
        return f"""<Dataset: {self.name}
        variables: {list(self.variables.keys())}
        time range: {self.time_range()}"""

    def __iter__(self):
        return self.variables.__iter__()

    def __contains__(self, item):
        return self.variables.__contains__(item)

    def plot(self, ax=None, **kwargs):
        for var in self.variables.values():
            if len(var):
                ax = var.plot(ax=ax)
        return ax
