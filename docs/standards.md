# Standards references for vendor-exit evidence

Phase 0 design references, checked 2026-11-19. These pins identify the material a reviewer can use to evaluate the proposed offline file contracts. Protocol interoperability would require separate conformance tests.

| Reference | Design target | Application |
|---|---|---|
| [Model Context Protocol](https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning) | 2026-07-28 | Record the declared protocol revision, logical tool name and input schema digest when supplied. Compare fixture declarations offline. A declaration alone cannot establish server availability or authorization. |
| [OpenTelemetry semantic conventions](https://github.com/open-telemetry/semantic-conventions/releases/tag/v1.45.0) and [GenAI conventions](https://github.com/open-telemetry/semantic-conventions-genai/tree/76e0c19e7fe11dc693fe258642363a438af4d3aa) | Core v1.45.0 and dedicated GenAI source revision 76e0c19e7fe11dc693fe258642363a438af4d3aa | Refer to provider, requested and response model, and token attributes where defined. Preserve absent measurements. Pin the mapping separately from the report format. ModelSwapBench already emits its own v1 mapping with a 1.30.0 schema URL. Preserve its reader compatibility. |
| [Agent2Agent specification release](https://github.com/a2aproject/A2A/releases/tag/v1.0.1) | v1.0.1 | An optional local Agent Card can identify declared skills and supported interfaces. Keep agent identity, authenticated principal and authorization bindings distinct. No endpoint discovery is needed for the report. |
| [Agentic AI Foundation project directory](https://aaif.io/projects/) | Directory snapshot consulted 2026-11-19 | Select individual projects by relevance. MCP provides a connector specification. AGENTS.md describes repository guidance. Foundation membership supplies neither a protocol version nor evidence of portability. |
| [JSON-LD](https://www.w3.org/TR/2020/REC-json-ld11-20200716/) | W3C Recommendation 1.1, 2020-07-16 | OpenOntologyLite uses a deterministic JSON-LD envelope for lossless local round trips. This target does not claim general RDF or OWL interoperability. |

Recheck upstream before implementation. Keep protocol versions, fixture schema versions and the scoring rubric independently identifiable in generated evidence.
