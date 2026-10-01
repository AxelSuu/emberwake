# 0018: Keyboard only for now

Status: accepted

## Context

Gamepad support (SDL game controller events, d-pad and stick navigation, button bindings) was
built in M1 and M4 but never played with a real pad. The pygbag build has no `CONTROLLER_*`
names, which crashed it at import, and every new screen had to carry button bindings, rebinding
rows and strings that nobody could test.

## Decision

Remove gamepad support. `Bindings` holds keys only, menu navigation is keyboard only, and the
controls screen lists keyboard actions. Settings go to version 5, which drops saved button
bindings.

## Consequences

- Less code and fewer strings while the game's feel is still being tuned.
- Adding a gamepad back later is a feature of its own: an `InputMapper` source, `Navigator`
  events, a `buttons` table in `Bindings` with a settings migration, and a controls section.
  It must not touch `pygame.CONTROLLER_*` at import time (the web build lacks them).
