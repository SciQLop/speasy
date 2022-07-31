import pyistp
from ...products import SpeasyVariable


def load_variable(variable="", file=None, buffer=None) -> SpeasyVariable or None:
    istp = pyistp.load(file=file, buffer=buffer)
    if istp and variable in istp.data_variables():
        var = istp.data_variable(variable)
        if len(var.axes) <= 2:
            if len(var.axes) == 2:
                y = var.axes[1].values.copy()
            else:
                y = None
            return SpeasyVariable(time=var.axes[0].values.copy(), data=var.values.copy(), meta=var.attributes, y=y,
                                  columns=var.labels)
