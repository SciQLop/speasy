import random
from typing import Any, Dict
from functools import wraps

"""
The rationale behind the following function is to randomize the order of execution so we minimize the requests collisions and maximize the throughput.
"""


def randomized_map(f, l, *args, **kwargs):
    """Applies function f to all elements in list l in a randomized order
    Parameters
    ----------
    f: function
        function to apply to each element in l
    l: list
        list of elements to process
    args: Any
        additional positional arguments to pass to f
    kwargs: Any
        additional keyword arguments to pass to f
    Returns
    -------
    list
        A list with the results of applying f to each element in l, in the original order
    Examples
    --------
    >>> randomized_map(lambda x: x**2, [1,2,3,4])
    [1, 4, 9, 16]
    """
    if not len(l):
        return []
    indexed_list = list(enumerate(l))
    random.shuffle(indexed_list)
    result = sorted([(i, f(e, *args, **kwargs)) for i, e in indexed_list], key=lambda x: x[0])
    return [e for i, e in result]


def pack_kwargs(**kwargs: Any) -> Dict:
    """Packs given keyword arguments into a dictionary

    Parameters
    ----------
    kwargs: Any
        Any keyword argument is accepted

    Returns
    -------
    dict
        A dict with all kwargs packed

    Examples
    --------
    >>> pack_kwargs(a=1, b="2")
    {'a': 1, 'b': '2'}
    """
    return kwargs


class AllowedKwargs(object):
    """A decorator that prevent from passing unexpected kwargs to a function
    """

    def __init__(self, allowed_list):
        self.allowed_list = set(allowed_list)

    def __call__(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            unexpected_args = list(
                filter(lambda arg_name: arg_name not in self.allowed_list, kwargs.keys()))
            if not unexpected_args:
                return func(*args, **kwargs)
            raise TypeError(
                f"Unexpected keyword argument {unexpected_args}, allowed keyword arguments are {self.allowed_list}")

        return wrapped


def fix_name(name: str):
    """Makes given input compatible with python charset https://docs.python.org/3/reference/lexical_analysis.html#identifiers

    Parameters
    ----------
    name: str
        input string to sanitize

    Returns
    -------
    str
        a string compatible with python naming rules


    Examples
    --------
    >>> fix_name('Parker Solar Probe (PSP)')
    'Parker_Solar_Probe_PSP'

    >>> fix_name('IS⊙ISEPI_Lo')
    'ISoISEPI_Lo'

    >>> fix_name('all_Legal_strings_123')
    'all_Legal_strings_123'

    """
    rules = (
        ('-', '_'),
        (':', '_'),
        ('.', '_'),
        ('(', ''),
        (')', ''),
        ('/', ''),
        (' ', '_'),
        ('{', ''),
        ('}', ''),
        ('(', ''),
        ('⊙', 'o'),
        (';', '_'),
        (',', '_'),
        ('%', '_')
    )
    if len(name):
        if name[0].isnumeric():
            name = "n_" + name
        for bad, replacement in rules:
            if bad in name:
                name = name.replace(bad, replacement)
        return name
    raise ValueError("Got empty name")
