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

`just` lists every task. `just run` continues save slot 1 (`--slot 2`, `--new` to start over);
`just run --room Test_Room` jumps straight into a room without loading or saving.

## Controls

| Action | Keyboard | Gamepad |
|---|---|---|
| Move | arrows / WASD | d-pad / left stick |
| Jump | Space, Z, C | A |
| Dash | X, Left Shift, K | X, B, RB |
| Interact (levers) | Up, W, E | Y, d-pad up |
| Drop through platform | Down + Jump | |
| Back to title | Esc | |

Bindings live in `settings.json` in the user data folder (Linux:
`~/.local/share/emberwake/emberwake/`).

Dev keys (`--dev`): F1 fps, F2 colliders, F3 free camera (drag with the mouse), F4 rooms, F5
reload `content/feel.toml` and the levels, F9 save a replay (play it with `--replay replays/<name>.json`),
P pause, `.` step one tick, `,` slow motion.

## Docs

- [Game design](docs/gdd.md)
- [Architecture](docs/architecture.md)
- [Art bible](docs/art-bible.md)
- [Roadmap](docs/roadmap.md)
- [Decision records](docs/adr/)

`just docs` serves the docs site with API reference generated from docstrings.
