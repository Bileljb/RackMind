"""Simulator settings from CLI flags, each falling back to an environment variable.

python -m rackmind_sim --fault overheat:R02:60:600 --fault memory_leak:r03-srv02:30:900
SIM_FAULTS="overheat:R02:60:600,disk_fill:r01-srv03:120:900" python -m rackmind_sim
"""

import argparse
import os
from dataclasses import dataclass

from rackmind_sim.faults import Fault, parse_fault


@dataclass(frozen=True)
class Config:
    api_url: str
    api_key: str  # sent as X-API-Key: the API only accepts metrics from holders of this key
    interval_s: float
    faults: list[Fault]
    seed: int | None  # same seed -> same noise, handy to reproduce a demo


def _fault_arg(spec: str) -> Fault:
    try:
        return parse_fault(spec)
    except ValueError as error:  # argparse shows ArgumentTypeError messages nicely
        raise argparse.ArgumentTypeError(str(error)) from None


def _env_faults() -> list[Fault]:
    specs = os.environ.get("SIM_FAULTS", "")
    return [parse_fault(spec) for spec in specs.split(",") if spec.strip()]


def parse_config(argv: list[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(prog="rackmind_sim", description=__doc__)
    parser.add_argument("--api-url", default=os.environ.get("SIM_API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("SIM_API_KEY", ""))
    parser.add_argument(
        "--interval", type=float, default=float(os.environ.get("SIM_INTERVAL_S", "5"))
    )
    parser.add_argument(
        "--fault",
        type=_fault_arg,
        action="append",
        dest="faults",
        help="kind:target:start_s:duration_s (repeatable). Overrides SIM_FAULTS.",
    )
    env_seed = os.environ.get("SIM_SEED")
    parser.add_argument("--seed", type=int, default=int(env_seed) if env_seed else None)
    args = parser.parse_args(argv)
    return Config(
        api_url=args.api_url,
        api_key=args.api_key,
        interval_s=args.interval,
        faults=args.faults if args.faults is not None else _env_faults(),
        seed=args.seed,
    )
