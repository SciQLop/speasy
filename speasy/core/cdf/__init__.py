import pyistp
from ...products import SpeasyVariable


def load_variable(variable="", file=None, buffer=None) -> SpeasyVariable or None:
    istp = pyistp.load(file=file, buffer=buffer)
    if istp:
        if variable in istp.data_variables():
            var = istp.data_variable(variable)
        elif variable.replace('-', '_') in istp.data_variables():  # THX CSA/ISTP
            var = istp.data_variable(variable.replace('-', '_'))
        else:
            return None
        if var:
            return SpeasyVariable(time=var.axes[0].values.copy(), values=var.values.copy(), meta=var.attributes,
                                  extra_axes=[ax.values.copy() for ax in var.axes[1:]],
                                  extra_axes_labels=[ax.name for ax in var.axes[1:]],
                                  columns=var.labels)
    return None
