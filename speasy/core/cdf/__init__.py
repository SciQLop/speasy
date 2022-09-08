import pyistp
from ...products import SpeasyVariable, VariableAxis, VariableTimeAxis, DataContainer


def _fix_value_type(value):
    if type(value) in (str, int, float):
        return value
    if type(value) is list:
        return [_fix_value_type(sub_v) for sub_v in value]
    return str(value)


def _fix_attributes_types(attributes: dict):
    cleaned = {}
    for key, value in attributes.items():
        cleaned[key] = _fix_value_type(value)
    return cleaned


def _make_axis(axis, time_axis_name):
    if axis.attributes.get('DEPEND_0', '') == time_axis_name:
        is_time_dependent = True
    else:
        is_time_dependent = False
    return VariableAxis(values=axis.values.copy(), meta=_fix_attributes_types(axis.attributes), name=axis.name,
                        is_time_dependent=is_time_dependent)


def load_variable(variable="", file=None, buffer=None) -> SpeasyVariable or None:
    istp = pyistp.load(file=file, buffer=buffer)
    if istp:
        if variable in istp.data_variables():
            var = istp.data_variable(variable)
        elif variable.replace('-', '_') in istp.data_variables():  # THX CSA/ISTP
            var = istp.data_variable(variable.replace('-', '_'))
        elif variable.replace('/', '$') in istp.data_variables():  # CDA
            var = istp.data_variable(variable.replace('/', '$'))
        else:
            return None
        if var:
            time_axis_name = var.axes[0].name
            return SpeasyVariable(
                axes=[VariableTimeAxis(values=var.axes[0].values.copy(),
                                       meta=_fix_attributes_types(var.axes[0].attributes))] + [
                         _make_axis(axis, time_axis_name) for axis in var.axes[1:]],
                values=DataContainer(values=var.values.copy(), meta=_fix_attributes_types(var.attributes),
                                     name=var.name,
                                     is_time_dependent=True),
                columns=var.labels)
    return None
