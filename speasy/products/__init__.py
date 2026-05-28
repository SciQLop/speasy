from .base_product import SpeasyProduct
from .catalog import Catalog, Event
from .dataset import Dataset
from .timetable import TimeTable
from .variable import DataContainer, SpeasyVariable, VariableAxis, VariableTimeAxis

MaybeAnyProduct = SpeasyProduct | list[SpeasyProduct] | None
MaybeTimeDependentProduct = SpeasyVariable | Dataset | None
MaybeTimeIndependentProduct = TimeTable | Catalog | None

__all__ = ['SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable', 'MaybeAnyProduct', 'MaybeTimeDependentProduct',
           'MaybeTimeIndependentProduct', 'VariableAxis', 'VariableTimeAxis', 'DataContainer']
