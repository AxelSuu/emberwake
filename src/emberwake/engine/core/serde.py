"""Convert dataclasses to and from JSON-compatible data using their type hints.

A tiny, dependency-free stand-in for pydantic (which cannot run in the browser build).
Supported types: ``None``, ``bool``, ``int``, ``float``, ``str``, ``Enum``, ``Literal``,
dataclasses, ``list[T]``, ``tuple[T, ...]``, ``tuple[A, B]``, ``dict[K, V]`` (``K`` is ``str``,
``int`` or an ``Enum``) and ``T | None``.

Loading is lenient where it helps save compatibility and strict where it catches bugs:
unknown keys are ignored, missing keys fall back to field defaults, wrong types raise
`SerdeError` with a JSONPath-like location. Fields declared with `alias` are stored under a
different key, for external formats whose keys are not valid Python names.

Example:
    >>> from dataclasses import dataclass
    >>> @dataclass
    ... class Point:
    ...     x: int
    ...     y: int = 0
    >>> from_data(Point, {"x": 3})
    Point(x=3, y=0)
    >>> to_data(Point(1, 2))
    {'x': 1, 'y': 2}
"""

from __future__ import annotations

import dataclasses
import functools
import types
import typing
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

type Data = bool | int | float | str | list[Data] | dict[str, Data] | None

SERDE_KEY = "serde_key"


class SerdeError(ValueError):
    """Raised when data does not match the expected type."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


def alias(key: str, **kwargs: Any) -> Any:
    """Declare a dataclass field stored under `key`; `kwargs` go to `dataclasses.field`."""
    return field(metadata={SERDE_KEY: key}, **kwargs)


def to_data(obj: object) -> Data:
    """Convert `obj` into JSON-compatible data."""
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj
    if isinstance(obj, Enum):
        return to_data(obj.value)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {_field_key(f): to_data(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, list | tuple):
        return [to_data(item) for item in obj]
    if isinstance(obj, dict):
        return {_key_to_str(key): to_data(value) for key, value in obj.items()}
    msg = f"cannot serialize {type(obj).__name__}"
    raise TypeError(msg)


def from_data[T](tp: type[T], data: object) -> T:
    """Build an instance of `tp` from JSON-compatible `data`."""
    return _convert(tp, data, "$")


@dataclass(frozen=True, slots=True)
class VersionedCodec[T]:
    """Wraps a model in a ``{"version": n, "data": ...}`` envelope with upgrade migrations.

    Attributes:
        model: Dataclass type stored in the envelope.
        version: Current schema version written by `dump`.
        migrations: ``migrations[n]`` upgrades raw data from version ``n`` to ``n + 1``.
    """

    model: type[T]
    version: int
    migrations: Mapping[int, Callable[[dict[str, Any]], dict[str, Any]]] = field(
        default_factory=dict
    )

    def dump(self, obj: T) -> dict[str, Data]:
        """Serialize `obj` at the current version."""
        return {"version": self.version, "data": to_data(obj)}

    def load(self, raw: object) -> T:
        """Migrate `raw` up to the current version and deserialize it."""
        if not isinstance(raw, dict) or not isinstance(raw.get("version"), int):
            raise SerdeError("$", "expected an object with an integer 'version'")
        version: int = raw["version"]
        data = raw.get("data")
        if version > self.version:
            raise SerdeError("$.version", f"{version} is newer than supported {self.version}")
        if not isinstance(data, dict):
            raise SerdeError("$.data", "expected an object")
        for step in range(version, self.version):
            if step not in self.migrations:
                raise SerdeError("$.version", f"no migration from version {step}")
            data = self.migrations[step](data)
        return from_data(self.model, data)


def _field_key(f: dataclasses.Field[Any]) -> str:
    return f.metadata.get(SERDE_KEY, f.name)


def _key_to_str(key: object) -> str:
    if isinstance(key, Enum):
        key = key.value
    if isinstance(key, str | int) and not isinstance(key, bool):
        return str(key)
    msg = f"cannot serialize dict key of type {type(key).__name__}"
    raise TypeError(msg)


@functools.cache
def _hints(cls: type) -> dict[str, Any]:
    return get_type_hints(cls)


def _convert(tp: Any, data: object, path: str) -> Any:  # noqa: PLR0911, PLR0912
    origin = get_origin(tp)
    args = get_args(tp)

    if tp is Any:
        return data
    if tp is None or tp is types.NoneType:
        if data is not None:
            raise SerdeError(path, "expected null")
        return None
    if origin in (Union, types.UnionType):
        return _convert_optional(args, data, path)
    if origin is Literal:
        if data not in args:
            raise SerdeError(path, f"expected one of {args!r}, got {data!r}")
        return data
    if isinstance(tp, typing.TypeAliasType):
        return _convert(tp.__value__, data, path)
    if isinstance(tp, type) and issubclass(tp, Enum):
        try:
            return tp(data)
        except ValueError:
            raise SerdeError(path, f"{data!r} is not a valid {tp.__name__}") from None
    if tp is bool:
        return _expect(data, bool, path)
    if tp is int:
        if isinstance(data, bool):
            raise SerdeError(path, "expected int, got bool")
        return _expect(data, int, path)
    if tp is float:
        if isinstance(data, bool) or not isinstance(data, int | float):
            raise SerdeError(path, f"expected float, got {type(data).__name__}")
        return float(data)
    if tp is str:
        return _expect(data, str, path)
    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        return _convert_dataclass(tp, data, path)
    if origin is list:
        items = _expect(data, list, path)
        return [_convert(args[0], item, f"{path}[{i}]") for i, item in enumerate(items)]
    if origin is tuple:
        return _convert_tuple(args, data, path)
    if origin is dict:
        mapping = _expect(data, dict, path)
        key_type, value_type = args
        return {
            _convert_key(key_type, key, path): _convert(value_type, value, f"{path}.{key}")
            for key, value in mapping.items()
        }
    msg = f"unsupported type {tp!r}"
    raise TypeError(msg)


def _expect[T](data: object, tp: type[T], path: str) -> T:
    if not isinstance(data, tp):
        raise SerdeError(path, f"expected {tp.__name__}, got {type(data).__name__}")
    return data


def _convert_optional(args: tuple[Any, ...], data: object, path: str) -> Any:
    options = [arg for arg in args if arg is not types.NoneType]
    if len(options) != 1 or len(args) != 2:
        msg = f"only `T | None` unions are supported, got {args!r}"
        raise TypeError(msg)
    return None if data is None else _convert(options[0], data, path)


def _convert_tuple(args: tuple[Any, ...], data: object, path: str) -> tuple[Any, ...]:
    items = _expect(data, list, path)
    if len(args) == 2 and args[1] is Ellipsis:
        return tuple(_convert(args[0], item, f"{path}[{i}]") for i, item in enumerate(items))
    if len(items) != len(args):
        raise SerdeError(path, f"expected {len(args)} items, got {len(items)}")
    pairs = zip(args, items, strict=True)
    return tuple(_convert(arg, item, f"{path}[{i}]") for i, (arg, item) in enumerate(pairs))


def _convert_key(key_type: Any, key: object, path: str) -> Any:
    if key_type is str:
        return key
    if key_type is int:
        try:
            return int(_expect(key, str, path))
        except ValueError:
            raise SerdeError(path, f"key {key!r} is not an int") from None
    if isinstance(key_type, type) and issubclass(key_type, Enum):
        member_type = type(next(iter(key_type)).value)
        return _convert(key_type, member_type(key), f"{path}.{key}")
    msg = f"unsupported dict key type {key_type!r}"
    raise TypeError(msg)


def _convert_dataclass(cls: Any, data: object, path: str) -> Any:
    mapping = _expect(data, dict, path)
    hints = _hints(cls)
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        if not f.init:
            continue
        key = _field_key(f)
        if key in mapping:
            kwargs[f.name] = _convert(hints[f.name], mapping[key], f"{path}.{key}")
        elif f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            raise SerdeError(f"{path}.{key}", "missing required field")
    return cls(**kwargs)
