from typing import List, Optional, Union

from .base_product import SpeasyProduct
from .catalog import Catalog, Event
from .dataset import Dataset
from .timetable import TimeTable
from .variable import DataContainer, SpeasyVariable, VariableAxis, VariableTimeAxis

MaybeAnyProduct = Optional[SpeasyProduct | list[SpeasyProduct]]
MaybeTimeDependentProduct = Optional[SpeasyVariable | Dataset]
MaybeTimeIndependentProduct = Optional[TimeTable | Catalog]

__all__ = ['SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable', 'MaybeAnyProduct', 'MaybeTimeDependentProduct',
           'MaybeTimeIndependentProduct', 'VariableAxis', 'VariableTimeAxis', 'DataContainer']
