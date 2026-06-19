# Memory Sidecar v3.5

Memory Sidecar v3.5 is the public beta release of the agent-agnostic memory sidecar.

It is designed for technical users who want to install the sidecar on their own agent home directory, connect it to Hindsight and gbrain, and provide real-world feedback on installation flow, recall quality, and multi-agent compatibility.

Release page: https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5

## Highlights

- Default install mode is `3`, which tries automatic dependency assistance first
- `--install-mode 3` is the default public path
- `2` and `1` are still available for guided or detection-only fallback
- Installer output supports English and Chinese
- Interactive embedding model selection is preserved
- Custom embedding model IDs are still supported
- The repository now includes a proper MIT `LICENSE`
- The homepage documentation and manual install guide are aligned with the actual installed script set
- `Knowledge-and-Memory-Management` is documented as the recommended upstream knowledge curation layer

## Feedback Targets

Please test and report on:

- install success rate
- clarity of the `3 -> 2 -> 1` fallback path
- bilingual output clarity
- embedding model selection flow
- knowledge note integration
- recall quality across multiple agents
- missing dependency handling on real systems

## Known Boundaries

This release still expects a working local environment:

- Python 3.9+
- PostgreSQL 16
- Hindsight
- gbrain
- a writable agent data directory

## Related Projects

- [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- [gbrain](https://github.com/hi-ogawa/gbrain)
