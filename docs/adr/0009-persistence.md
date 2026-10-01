# 0009 Storage abstraction, versioned JSON, atomic writes

**Context.** Settings, saves, records and ghosts must survive crashes, schema changes and run in
the browser.

**Decision.** `Storage` protocol with file (pref dir), memory and `localStorage` backends. Documents
are JSON in a `{"version", "data"}` envelope, migrated step by step by `VersionedCodec`. File
writes go through a temp file and `os.replace`, keep one `.bak`, and unreadable documents are
preserved as `.corrupt` before defaults are used.

**Consequences.** Every model change needs a version bump and migration (with a test). Saves are
human-readable and easy to debug.
