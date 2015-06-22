def identity(x):
    return x

def cond_set(item, key, values, conv=identity):
    """Conditionally sets the first element of the given iterable to the given
    dict.

    The condition is that the key is not set in the item or its value is None.
    Also, the value to be set must not be None.
    """
    try:
        if values:
            value = next(iter(values))
            cond_set_value(item, key, value, conv)
    except StopIteration:
        pass


def cond_set_value(item, key, value, conv=identity):
    """Conditionally sets the given value to the given dict.

    The condition is that the key is not set in the item or its value is None.
    Also, the value to be set must not be None.
    """
    if item.get(key) is None and value is not None and conv(value) is not None:
        item[key] = conv(value)