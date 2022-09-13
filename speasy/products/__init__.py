from .base_product import SpeasyProduct
from .catalog import Catalog, Event
from .timetable import TimeTable
from .dataset import Dataset
from .variable import SpeasyVariable, VariableTimeAxis, VariableAxis, DataContainer
from typing import Optional, Union, List

MaybeAnyProduct = Optional[Union[SpeasyProduct, List[SpeasyProduct]]]
MaybeTimeDependentProduct = Optional[Union[SpeasyVariable, Dataset]]
MaybeTimeIndependentProduct = Optional[Union[TimeTable, Catalog]]

__all__ = ['SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable', 'MaybeAnyProduct', 'MaybeTimeDependentProduct',
           'MaybeTimeIndependentProduct', 'VariableAxis', 'VariableTimeAxis', 'DataContainer']
