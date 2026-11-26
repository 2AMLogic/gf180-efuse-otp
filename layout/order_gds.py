"""Give consecutive GDSII BOUNDARY elements a deterministic order.

KLayout's spatial traversal can visit contact and fill polygons in different
orders on different platforms. Sort the final writer's complete element bytes
(including properties) within each run. All other records, including cell
headers, text and instance arrays, stay at their original byte offsets.
"""

import struct
import sys
from pathlib import Path


BOUNDARY = 0x0800
ENDEL = 0x1100
RECORD_HEADER = struct.Struct(">HH")


def order_boundaries(stream):
    output = bytearray()
    boundaries = []
    start = None
    offset = 0
    while offset < len(stream):
        size, kind = RECORD_HEADER.unpack_from(stream, offset)
        end = offset + size
        if size < RECORD_HEADER.size or size % 2 or end > len(stream):
            raise ValueError(f"invalid GDS record length {size} at {offset}")

        if kind == BOUNDARY:
            if start is not None:
                raise ValueError(f"nested BOUNDARY at {offset}")
            start = offset
        elif start is not None:
            if kind == ENDEL:
                boundaries.append(stream[start:end])
                start = None
        else:
            if boundaries:
                output.extend(b"".join(sorted(boundaries)))
                boundaries.clear()
            output.extend(stream[offset:end])
        offset = end

    if start is not None or boundaries:
        raise ValueError("GDS ended before the end of the structure")
    return output


if __name__ == "__main__":
    source, destination = map(Path, sys.argv[1:])
    destination.write_bytes(order_boundaries(source.read_bytes()))
