from .catalog import Catalog, Event
from .timetable import TimeTable
from .dataset import Dataset
from .variable import SpeasyVariable, VariableTimeAxis, VariableAxis, DataContainer
from typing import Optional, Union

MaybeAnyProduct = Optional[Union[Dataset, SpeasyVariable, Catalog, TimeTable]]
