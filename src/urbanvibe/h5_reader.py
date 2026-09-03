from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FebusReadResult:
    trace: Any
    distance: Any
    time: Any
    attributes: dict[str, Any]


def _first_last(values):
    if values is None:
        return None, None
    seq = list(values)
    if not seq:
        return None, None
    return seq[0], seq[-1]


def _infer_window(instance, zone: str):
    """Infer full distance/time window by probing the zone vectors."""
    probe = instance.extract_concat(
        from_time=None,
        to_time=None,
        time_type="timestamp",
        from_dist=None,
        to_dist=None,
        dist_type="meter",
        zones=zone,
    )
    zone_probe = probe[zone]

    dist_start, dist_end = _first_last(zone_probe.get("distance_vect"))
    time_start, time_end = _first_last(zone_probe.get("time_vect"))

    if dist_start is None or dist_end is None or time_start is None or time_end is None:
        raise ValueError(
            "Could not infer full distance/time window from file. "
            "Provide d1 d2 t_start t_end explicitly."
        )

    return float(dist_start), float(dist_end), str(time_start), str(time_end)


def read_h5_file(h5_file, d1=None, d2=None, t_start=None, t_end=None) -> FebusReadResult:
    """Read an HDF5 DAS file using FEBUS for a distance and time window."""
    try:
        import febus_optics_lib.reader as reader
    except ImportError as exc:
        raise ImportError(
            "febus_optics_lib is required for read_h5_file. Install it in your environment."
        ) from exc

    instance = reader.H5ReaderDas(h5_file)

    attributes_dict = dict(instance._hdf5_dict)
    zone = instance.list_zones[0]
    param_dict = instance.param_dict[zone]
    attributes_dict["param_dict"] = param_dict

    if d1 is None or d2 is None or t_start is None or t_end is None:
        d1_i, d2_i, t_start_i, t_end_i = _infer_window(instance, zone)
        d1 = d1 if d1 is not None else d1_i
        d2 = d2 if d2 is not None else d2_i
        t_start = t_start if t_start is not None else t_start_i
        t_end = t_end if t_end is not None else t_end_i

    concat_results = instance.extract_concat(
        from_time=t_start,
        to_time=t_end,
        time_type="timestamp",
        from_dist=d1,
        to_dist=d2,
        dist_type="meter",
        zones=zone,
    )

    zone_results = concat_results[zone]
    return FebusReadResult(
        trace=zone_results["data"],
        distance=zone_results["distance_vect"],
        time=zone_results["time_vect"],
        attributes=attributes_dict,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read HDF5 DAS data via FEBUS reader.")
    parser.add_argument("h5_file", help="Path to input .h5 file")
    parser.add_argument("d1", type=float, nargs="?", default=None, help="Start distance in meters")
    parser.add_argument("d2", type=float, nargs="?", default=None, help="End distance in meters")
    parser.add_argument("t_start", nargs="?", default=None, help="Start timestamp")
    parser.add_argument("t_end", nargs="?", default=None, help="End timestamp")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    result = read_h5_file(
        h5_file=args.h5_file,
        d1=args.d1,
        d2=args.d2,
        t_start=args.t_start,
        t_end=args.t_end,
    )

    print(f"Read successful: trace_shape={getattr(result.trace, 'shape', 'unknown')}")
    print(f"Distance samples: {len(result.distance)}")
    print(f"Time samples: {len(result.time)}")
    print(f"Metadata keys: {len(result.attributes)}")


if __name__ == "__main__":
    main()
