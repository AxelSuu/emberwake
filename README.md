# Emberwake

A pixel-art action-platformer about carrying light into the dark. Built with
[pygame-ce](https://pyga.me), runs on desktop and in the browser (pygbag).

## Quick start

```sh
uv sync            # install (needs uv: https://docs.astral.sh/uv/)
just run --dev     # play, F1 toggles the debug overlay, F11 fullscreen
just check         # ruff, ty, import contracts
just test          # headless test suite
just web           # browser build into build/web
```

`just` lists every task.

## Docs

- [Game design](docs/gdd.md)
- [Architecture](docs/architecture.md)
- [Art bible](docs/art-bible.md)
- [Roadmap](docs/roadmap.md)
- [Decision records](docs/adr/)

`just docs` serves the docs site with API reference generated from docstrings.
