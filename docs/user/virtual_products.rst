Virtual products
================

A virtual product is not data downloaded from a web service, it is a local
function dynamically computing a product.

You register your function with an inventory path, and then use it as any other
Speasy product: request it with :func:`speasy.get_data`, or call it by its name.

The registration can be done either directly, or with the decorator
:func:`speasy.virtual_products.register_virtual_product`.


Writing the function
--------------------

The user function to register takes a time range as argument ``(start_time,
stop_time)`` and returns a ``SpeasyVariable``, or ``None`` when there is no
data.
It receives the time range exactly as it was given to :func:`speasy.get_data`:

    >>> import pandas as pd
    >>> import speasy as spz
    >>> def hourly_ramp(start_time, stop_time):
    ...     index = pd.date_range(start_time, stop_time, freq=pd.Timedelta(hours=1), inclusive="left")
    ...     return spz.SpeasyVariable.from_dataframe(pd.DataFrame({"ramp": range(len(index))}, index=index))

Registering with a decorator
----------------------------

The registering path must start with ``virtual/``, followed by the inventory
path of your choice (e.g. ``virtual/demo/ramp``).

After the decorator, the function name refers to the product, and the function
is registered in the inventory tree:

    >>> from speasy.virtual_products import register_virtual_product
    >>> @register_virtual_product("virtual/demo/ramp")
    ... def ramp(start_time, stop_time):
    ...     return hourly_ramp(start_time, stop_time)
    >>> spz.inventories.tree.virtual.demo.ramp is ramp
    True

Registering directly without a decorator
----------------------------------------

Pass the function as second argument; the product is returned:

    >>> slope = register_virtual_product("virtual/demo/slope", hourly_ramp)
    >>> spz.inventories.tree.virtual.demo.slope is slope
    True

Using a virtual product
-----------------------

By path, by the decorated name, through the inventory tree, or by a direct call:

    >>> spz.get_data("virtual/demo/ramp", "2016-10-10", "2016-10-11").shape
    (24, 1)
    >>> spz.get_data(ramp, "2016-10-10", "2016-10-11").shape
    (24, 1)
    >>> spz.get_data(spz.inventories.tree.virtual.demo.ramp, "2016-10-10", "2016-10-11").shape
    (24, 1)
    >>> ramp("2016-10-10", "2016-10-11").shape
    (24, 1)

Good to know
------------

- Registering again at the same path replaces the previous product and emits a warning, which is
  convenient when iterating in a notebook.
- Requesting a path that was never registered raises ``UnknownVirtualProduct``, a ``ValueError``.
- If the function returns anything other than a ``SpeasyVariable`` or ``None``, :func:`speasy.get_data`
  raises a ``TypeError`` naming the function.
