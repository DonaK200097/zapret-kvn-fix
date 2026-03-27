# Profile Format V1

## Status

Draft working specification.

This document fixes the current direction for profile-based routing configuration.
It is intended to be reviewed, updated, and used as the basis for implementation.

## Goals

- Replace GUI-first routing configuration with self-contained profile files.
- Keep the product simple for novice users.
- Preserve a GUI workflow for loading, saving, previewing, editing, and applying profiles.
- Support multiple runtime engines without pretending they all support the same features.
- Fail hard on invalid profiles instead of applying them partially.

## Product Direction

- Source of truth for routing is a profile file.
- GUI is not the source of truth anymore.
- GUI remains useful for:
  - loading a profile
  - saving a profile
  - applying a profile
  - previewing compiled rules
  - editing the simple DSL
  - showing validation errors

## File Format

- Format: `TOML`
- One profile = one file
- The file is self-contained except for references to existing nodes
- The profile stores its own user-facing name

## Node References

Profiles do not store full server definitions.

Server definitions continue to live in the existing `nodes` storage.

Profiles reference a server only by `node_id`.

### Node ID Rules

- `node_id` is the existing `Node.id` field
- `node_id` becomes user-visible and user-editable in the GUI
- `node_id` must be unique
- If a profile references an unknown `node_id`, the profile is invalid and must not be applied

### Recommended Node ID Constraints

- ASCII only
- lowercase only
- allowed characters: `a-z`, `0-9`, `_`, `-`
- no spaces
- length: `3..64`

Examples:

- `nl_fast_1`
- `discord_ru`
- `wg_home`
- `de_stream`

## Profile Structure

Minimal shape:

```toml
version = 1
name = "Discord Fast"
description = "Discord through a dedicated node"

[meta]
author = "team"
created = "2026-03-27"
updated = "2026-03-27"

[engines."sing-box"]
default = 'active'
rules = [
  'app "Discord.exe" -> node nl_fast_1',
  'app_dir "W:\\Users\\Privacy\\AppData\\Local\\Discord\\" -> node nl_fast_1',
  'domain "*.discord.com" -> node nl_fast_1',
]

[engines.xray]
default = 'active'
rules = [
  'app "Discord.exe" -> node nl_fast_1',
  'domain "*.discord.com" -> node nl_fast_1',
]

[engines.wireguard]
default = 'direct'
rules = [
  'domain "*.discord.com" -> node nl_fast_1',
]
```

## Multi-Engine Model

Profiles contain separate DSL blocks for each engine.

Current decision:

- no shared `common` block in V1
- no fake cross-engine abstraction in V1
- each engine gets its own explicit rules
- each engine must explicitly define how unmatched traffic is handled via `default`

Rationale:

- real engine capability must be studied first
- profiles must be correct from the start
- users should not need to rewrite profiles after load because the app guessed wrong

## Rule Model

Rules are evaluated:

- top to bottom
- first match wins

This order is part of the profile itself.

If no rule matches, the engine must use the engine-level `default` action.

`default` is required for every engine block.

Allowed `default` values in V1:

- `direct`
- `block`
- `active`
- `node <node_id>`

Meaning of `active`:

- use the node currently selected by the user in the GUI
- if no node is currently selected in the GUI, profile application must fail

## DSL V1

### Supported Match Types

- `app`
- `app_path`
- `app_dir`
- `domain`
- `ip`

### Supported Actions

- `direct`
- `block`
- `node <node_id>`
- `node`
- `active`

### Canonical Examples

```txt
app "Discord.exe" -> node nl_fast_1
app_path "W:\\Users\\Privacy\\AppData\\Local\\Discord\\app-1.0.9210\\Discord.exe" -> block
app_dir "W:\\Users\\Privacy\\AppData\\Local\\Discord\\" -> node nl_fast_1
domain "*.discord.com" -> node nl_fast_1
ip "1.2.3.0/24" -> direct
```

If a rule targets a node but does not specify a concrete `node_id`, the active node must be used.

Canonical shorthand forms:

```txt
app "Discord.exe" -> node
domain "*.discord.com" -> active
```

Both mean: use the node currently selected by the user in the GUI.

## DSL Grammar V1

This is the intended grammar shape for the first implementation.

```ebnf
rule        = match, ws, "->", ws, action ;

match       = app_match | app_path_match | app_dir_match | domain_match | ip_match ;

app_match       = "app", ws, quoted_string ;
app_path_match  = "app_path", ws, quoted_string ;
app_dir_match   = "app_dir", ws, quoted_string ;
domain_match    = "domain", ws, quoted_string ;
ip_match        = "ip", ws, quoted_string ;

action      = "direct" | "block" | "active" | node_action ;
node_action = "node" | ("node", ws, identifier) ;

quoted_string = DQUOTE, { any_char_except_dquote }, DQUOTE ;
identifier    = identifier_start, { identifier_continue } ;
identifier_start = "a".."z" | "_" ;
identifier_continue = identifier_start | "0".."9" | "-" ;
ws            = { " " | "\t" } ;
```

## DSL Semantics V1

### `app`

Matches by executable name.

Example:

```txt
app "Discord.exe" -> node nl_fast_1
app "Discord.exe" -> node
```

### `app_path`

Matches one exact executable path.

Example:

```txt
app_path "W:\\Users\\Privacy\\AppData\\Local\\Discord\\app-1.0.9210\\Discord.exe" -> block
```

### `app_dir`

Matches executables under a directory tree.

Intended meaning:

- the path is treated as a directory root
- executables under that root are matched

Example:

```txt
app_dir "W:\\Users\\Privacy\\AppData\\Local\\Discord\\" -> node nl_fast_1
app_dir "W:\\Users\\Privacy\\AppData\\Local\\Discord\\" -> node
```

### `domain`

Matches a domain or domain wildcard.

Examples:

```txt
domain "discord.com" -> node nl_fast_1
domain "*.discord.com" -> node nl_fast_1
domain "*.discord.com" -> active
```

### `ip`

Matches a single IP or CIDR.

Examples:

```txt
ip "1.2.3.4" -> direct
ip "1.2.3.0/24" -> direct
```

## Active Node Semantics

The profile format supports using the currently selected node from the program.

This is allowed in two forms:

- `active`
- `node` without a quoted `node_id`

Examples:

```txt
app "Discord.exe" -> active
app "Discord.exe" -> node
```

Both mean:

- resolve to the runtime-resolved current node from the program

Validation rules:

- if the engine block uses `active` or bare `node`, the application must resolve the current node from the GUI-selected node only
- if no node is selected in the GUI, profile application must fail with a clear error
- `active` is not a stored node reference; it is a runtime binding to the current GUI-selected node

## Validation Rules

A profile must not be applied unless all checks pass.

### Syntax Validation

The parser must reject:

- unknown keywords
- malformed quoted strings
- missing `->`
- malformed actions
- malformed rule lines

### Semantic Validation

The validator must reject:

- unsupported match types for an engine
- unsupported actions for an engine
- invalid domain patterns
- invalid path forms
- invalid IP or CIDR
- missing required `default` in an engine block
- use of `active` or bare `node` when the runtime has no GUI-selected node

### Reference Validation

The validator must reject:

- unknown `node_id`
- duplicate or conflicting node references when the engine disallows them

## Error Handling

Any validation error is fatal for profile application.

Required behavior:

- the profile is not applied
- the editor highlights the problem
- the GUI shows exactly where and why it failed

Expected error payload:

- engine
- line number
- column number when available
- short error kind
- human-readable explanation

Examples:

- `line 3: unknown node_id "discord_fast_1"`
- `line 2: expected action after '->'`
- `line 5: engine 'wireguard' does not support app_path`
- `engine 'sing-box': missing required default action`
- `line 4: current node is required but no node is selected in the GUI`

## Valid and Invalid Rule Examples

### Valid

```txt
app "Discord.exe" -> node nl_fast_1
app "Discord.exe" -> node
app "Discord.exe" -> active
app_path "W:\\Users\\Privacy\\AppData\\Local\\Discord\\app-1.0.9210\\Discord.exe" -> block
app_dir "W:\\Users\\Privacy\\AppData\\Local\\Discord\\" -> direct
domain "*.discord.com" -> node nl_fast_1
domain "discord.com" -> active
ip "1.2.3.4" -> direct
ip "1.2.3.0/24" -> block
```

### Invalid

```txt
app Discord.exe -> node nl_fast_1
```

Reason:

- executable name must be quoted

```txt
app "Discord.exe" node nl_fast_1
```

Reason:

- missing `->`

```txt
app_path "W:\\Users\\Privacy\\AppData\\Local\\Discord\\Discord.exe" -> node
```

Reason:

- this is valid syntax and means "use the current GUI-selected node"

The invalid version is:

```txt
app_path "W:\\Users\\Privacy\\AppData\\Local\\Discord\\Discord.exe" -> node "nl_fast_1"
```

Reason:

- `node_id` must not be quoted

```txt
domain "*.discord.com" -> node missing_node
```

Reason:

- unknown `node_id`

```txt
ip "not_an_ip" -> direct
```

Reason:

- invalid IP/CIDR literal

```txt
folder "W:\\Users\\Privacy\\AppData\\Local\\Discord\\" -> direct
```

Reason:

- unknown match keyword, use `app_dir`

## GUI Scope V1

The GUI must support:

- loading a profile file
- saving a profile file
- applying a profile
- showing the active profile name
- highlighting the active profile in the profile menu
- previewing compiled rules
- editing the simple DSL
- showing syntax and validation errors inline

The GUI does not need to provide:

- a visual rule builder
- automatic repair of invalid profiles
- hidden fallback behavior

## Examples

### Example A

```toml
version = 1
name = "Discord Fast"

[engines."sing-box"]
default = 'active'
rules = [
  'app "Discord.exe" -> node nl_fast_1',
  'app_dir "W:\\Users\\Privacy\\AppData\\Local\\Discord\\" -> node nl_fast_1',
  'domain "*.discord.com" -> node nl_fast_1',
  'domain "*.discord.gg" -> node nl_fast_1',
]

[engines.xray]
default = 'active'
rules = [
  'app "Discord.exe" -> node nl_fast_1',
  'domain "*.discord.com" -> node nl_fast_1',
  'domain "*.discord.gg" -> node nl_fast_1',
]

[engines.wireguard]
default = 'direct'
rules = [
  'domain "*.discord.com" -> node nl_fast_1',
  'domain "*.discord.gg" -> node nl_fast_1',
]
```

### Example B

```toml
version = 1
name = "Strict Split"

[engines."sing-box"]
default = 'active'
rules = [
  'app "Discord.exe" -> node nl_fast_1',
  'app "qbittorrent.exe" -> direct',
  'domain "*.microsoft.com" -> direct',
  'domain "*.doubleclick.net" -> block',
  'ip "10.0.0.0/8" -> direct',
]

[engines.xray]
default = 'active'
rules = [
  'app "Discord.exe" -> node nl_fast_1',
  'app "qbittorrent.exe" -> direct',
  'domain "*.microsoft.com" -> direct',
  'domain "*.doubleclick.net" -> block',
]

[engines.wireguard]
default = 'direct'
rules = [
  'domain "*.microsoft.com" -> direct',
  'domain "*.doubleclick.net" -> block',
]
```

## Not In Scope For V1

- server groups
- references to the current selected node
- inheritance between profiles
- one shared abstract ruleset compiled automatically to all engines
- partial apply with warnings
- automatic fallback to other nodes
- advanced boolean logic such as `all`, `any`, `not`

## Open Questions

These must be answered by engine capability research before the final implementation:

- exact support matrix for `app`, `app_path`, `app_dir`, `domain`, `ip`
- exact meaning of folder matching per engine
- exact support for `block` and named outbound routing per engine
- exact runtime apply behavior per engine
- exact Windows limitations per engine
