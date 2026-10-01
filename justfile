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

# Generate normal maps (_n.png) for sprites in assets/
normals:
    uv run python -m tools.normals

# Expand 4 source tiles into a 47-tile blob set: just autotile art/tiles/ground.png
autotile *args:
    uv run python -m tools.autotile {{args}}

# Generate sound effects from sfx/*.toml into assets/sfx/
sfx *args:
    uv run python -m tools.sfx {{args}}

# Recompile sprites whenever they change
art-watch:
    uv run python -m tools.pxl watch

web-stage: sfx
    rm -rf build/web-src && mkdir -p build/web-src
    cp main.py build/web-src/
    cp -r src/emberwake content levels build/web-src/
    if [ -d assets ]; then cp -r assets build/web-src/; fi
    if [ -n "$(find build/web-src -name "*.wav" 2>/dev/null)" ]; then echo "warning: pygbag rejects WAV; leaving sounds out (install ffmpeg or oggenc)"; find build/web-src -name "*.wav" -delete; fi

# Build the browser version into build/web
web: web-stage
    uv run --group web pygbag --build build/web-src
    rm -rf build/web && mv build/web-src/build/web build/web

# Build and serve the browser version on http://localhost:8000 (needed on localhost: it serves /cdn)
web-serve: web-stage
    uv run --group web pygbag build/web-src

docs:
    uv run --group docs mkdocs serve

profile *args:
    uv run python -m cProfile -o build/profile.prof -m emberwake {{args}}
