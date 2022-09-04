from typing import List, Tuple, Any, Sequence, Union, Optional


def span_ctor(span_type, start, stop):
    if start <= stop:
        if span_type is list or span_type is tuple:
            return span_type((start, stop))
        else:
            return span_type(start, stop)
    else:
        return None


def is_span(maybe_span: Any) -> bool:
    return hasattr(maybe_span, '__getitem__') and len(maybe_span) == 2 and maybe_span[0] <= maybe_span[1]


def is_empty(span: Sequence) -> bool:
    return span[0] == span[1]


def intersection(span: Sequence, other: Sequence) -> Optional[Sequence]:
    if not is_span(span) or not is_span(other):
        raise TypeError("You must provide a Span like object")
    if other[0] > span[1] or span[0] > other[1]:
        return None
    else:
        return span_ctor(type(span), max(span[0], other[0]), min(span[1], other[1]))


def intersects(span: Sequence, other: Sequence) -> bool:
    return intersection(span, other) is not None


def contains(span: Sequence, other: Sequence) -> bool:
    if not is_span(span) or not is_span(other):
        raise TypeError("You must provide a Span like object")
    return span[0] <= other[0] <= span[1] and span[1] >= other[1] >= span[0]


def equals(span: Sequence, other: Sequence) -> bool:
    if not is_span(span) or not is_span(other):
        raise TypeError("You must provide a Span like object")
    return span[0] == other[0] and span[1] == other[1]


def merge(spans: Union[List[Sequence], Tuple[Sequence]]) -> List[Sequence]:
    assert all([is_span(span) for span in spans])
    merged_list = []
    spans.sort(key=lambda item: item[0])
    while len(spans):
        current_span = spans.pop(0)
        while len(spans):
            if current_span[1] >= spans[0][0]:
                current_span[1] = max(current_span[1], spans[0][1])
                spans.pop(0)
            else:
                break
        merged_list.append(current_span)
    return merged_list


def difference(span: Sequence, other_s: Sequence) -> List[Sequence]:
    if not is_span(span) or not is_span(other_s):
        raise TypeError("You must provide a Span like object")

    diff = [
        span_ctor(type(span), span[0], min(other_s[0], span[1])),
        span_ctor(type(span), max(other_s[1], span[0]), span[1])
    ]
    diff = [part for part in diff if part is not None and not is_empty(part)]
    return diff


def zoom(span: Sequence, factor: float):
    if not is_span(span):
        raise TypeError("You must provide a Span like object")
    if type(factor) is not float and type(factor) is not int:
        raise TypeError("factor must be float")

    width = (span[1] - span[0]) / 2
    center = span[0] + width
    width *= factor
    return span_ctor(type(span), center - width, center + width)


def shift(span: Sequence, distance):
    if not is_span(span):
        raise TypeError("You must provide a Span like object")
    return span_ctor(type(span), span[0] + distance, span[1] + distance)


def split(span: Sequence, fragment_duration) -> List[Sequence]:
    from math import ceil
    if not is_span(span):
        raise TypeError("You must provide a Span like object")
    total_duration = span[1] - span[0]
    if total_duration <= fragment_duration:
        return [span]
    fragments = [
        span_ctor(type(span), span[0] + fragment_duration * i, min(span[0] + fragment_duration * (i + 1), span[1])) for
        i in range(ceil(total_duration / fragment_duration))]
    return fragments
