set shell := ["bash", "-cu"]
export SDL_AUDIODRIVER := env("SDL_AUDIODRIVER", "dummy")

default:
    @just --list

# Run the game (extra args go to the CLI, e.g. `just run --dev`)
run *args:
    SDL_AUDIODRIVER= uv run emberwake {{args}}

# Lint, format check, types, architecture contracts
check:
    uv run ruff check .
    uv run ruff format --check .
    uv run ty check
    uv run lint-imports
    uv run python -m tools.levels validate
    uv run python -m tools.palette lint

fix:
    uv run ruff check --fix .
    uv run ruff format .

test *args:
    SDL_VIDEODRIVER=dummy uv run pytest {{args}}

# Time the benchmarks and check their budgets
bench *args:
    SDL_VIDEODRIVER=dummy uv run pytest tests/bench --benchmark-enable {{args}}

cov:
    SDL_VIDEODRIVER=dummy uv run pytest --cov --cov-report=term-missing

# Compile pixel DSL sprites from art/ into assets/
art:
    uv run python -m tools.pxl build

# Pack assets/ into albedo, normal and emissive atlases under build/atlas/
atlas:
    uv run python -m tools.atlas

# Recompile sprites whenever they change
art-watch:
    uv run python -m tools.pxl watch

# Build the browser version into build/web
web:
    rm -rf build/web-src && mkdir -p build/web-src
    cp main.py build/web-src/
    cp -r src/emberwake content levels build/web-src/
    uv run --group web pygbag --build build/web-src
    rm -rf build/web && mv build/web-src/build/web build/web

# Serve the browser version on http://localhost:8000
web-serve: web
    uv run --group web pygbag build/web-src

docs:
    uv run --group docs mkdocs serve

profile *args:
    uv run python -m cProfile -o build/profile.prof -m emberwake {{args}}
