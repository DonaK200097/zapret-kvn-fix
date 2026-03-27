# Engine Capability Research

## Purpose

This document defines what must be verified before finalizing the per-engine DSL implementation for profile-based routing.

The profile format uses separate rule blocks per engine. That means each engine must be studied directly, not guessed.

Target engines:

- `sing-box`
- `xray`
- `wireguard`

## Core Questions

For each engine, verify the following.

### Match Capabilities

- supports match by executable name
- supports match by exact executable path
- supports match by application directory
- supports match by domain
- supports match by IP
- supports match by CIDR

### Action Capabilities

- supports `direct`
- supports `block`
- supports routing to a specific node/outbound
- supports engine-level default handling for unmatched traffic
- supports binding to the node currently selected in the GUI

### Runtime Scope

- works in TUN mode
- works in proxy mode
- works on Windows
- requires administrator rights

### Rule Processing

- top-to-bottom order
- first-match-wins
- any engine-specific exceptions or hidden priorities

### Reload / Apply Behavior

- supports live reload
- requires reconnect
- recreates TUN adapter
- can apply per-rule changes without tearing down the session

### Error Model

- how syntax errors surface
- how unsupported features surface
- whether invalid rules fail hard or degrade silently

## Required Output

For each engine, we need a capability matrix and implementation notes.

## Matrix Template

| Capability | sing-box | xray | wireguard | Notes |
| --- | --- | --- | --- | --- |
| app name | TODO | TODO | TODO | |
| app exact path | TODO | TODO | TODO | |
| app directory | TODO | TODO | TODO | |
| domain | TODO | TODO | TODO | |
| IP | TODO | TODO | TODO | |
| CIDR | TODO | TODO | TODO | |
| direct | TODO | TODO | TODO | |
| block | TODO | TODO | TODO | |
| specific node/outbound | TODO | TODO | TODO | |
| engine default for unmatched traffic | TODO | TODO | TODO | |
| runtime binding to GUI-selected node | TODO | TODO | TODO | |
| first match wins | TODO | TODO | TODO | |
| TUN mode | TODO | TODO | TODO | |
| proxy mode | TODO | TODO | TODO | |
| live reload | TODO | TODO | TODO | |

## Research Notes Per Engine

### sing-box

To verify:

- process name support
- process path support
- process path regex or equivalent folder matching
- route order semantics
- direct/block/named outbound behavior
- default action behavior for unmatched traffic
- whether the GUI-selected node can be mapped cleanly to a generated outbound
- TUN behavior on Windows
- reload behavior and adapter recreation behavior

### xray

To verify:

- process matching support in proxy mode
- exact path and folder behavior
- route order semantics
- direct/block/outbound routing
- default action behavior for unmatched traffic
- whether the GUI-selected node can be mapped cleanly to a generated outbound
- reload behavior

### wireguard

To verify:

- whether application-level matching exists at all in the intended usage model
- whether only domain/IP-based policy is realistic
- whether routing to a specific node concept maps cleanly
- whether unmatched traffic default must be expressed explicitly in generated config
- whether the GUI-selected node can be mapped cleanly to a generated outbound
- what must be forbidden in the wireguard engine DSL

## Decision Rule

A DSL construct must not be finalized for an engine until it is confirmed by direct capability research.

If an engine does not support a construct:

- the validator must reject that rule for that engine
- the profile must not be applied

No silent downgrade is allowed in V1.
