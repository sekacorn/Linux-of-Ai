# Start Here: How to Use Linux of AI

This guide helps you choose a practical first project in the Linux of AI ecosystem.

## What Linux of AI is

Linux of AI is a free, open-source ecosystem for building portable, governed, measurable, and replaceable AI infrastructure so organizations are not locked into one AI vendor, model, or platform.

## What problem are you trying to solve?

### 1. I want to reduce AI vendor lock-in

Start with:

- ModelSwapBench
- AIMeter OSS
- AIAuditLog

Recommended first step:

- Run the [Linux of AI Vendor Exit Demo](../examples/vendor-exit-demo/).

ModelSwapBench helps compare a baseline model against a candidate replacement model. AIMeter OSS helps measure estimated cost, usage, efficiency, and outcomes. AIAuditLog helps record portable audit evidence.

### 2. I want private or local AI infrastructure

Start with:

- PrivateAIStack
- AgentForge

PrivateAIStack provides a local-first controlled deployment starter. AgentForge helps orchestrate agent workflows and model routing.

### 3. I want governed AI agents

Start with:

- AgentPolicyPack
- AgentForge
- AIAuditLog

AgentPolicyPack defines portable policy rules. AgentForge applies orchestration patterns. AIAuditLog records operational evidence.

### 4. I want portable business meaning

Start with:

- OpenOntologyLite
- AgentPolicyPack

OpenOntologyLite defines entities, relationships, actions, permissions, and business meaning outside one vendor platform. AgentPolicyPack can use that meaning to govern behavior.

### 5. I want to measure AI cost and outcomes

Start with:

- AIMeter OSS
- ModelSwapBench

AIMeter OSS measures estimated cost, usage, efficiency, budgets, and outcomes. ModelSwapBench helps compare models and estimate replacement tradeoffs.

## Quick decision map

| Need | Start with |
|---|---|
| Replace or compare models | ModelSwapBench |
| Measure AI cost, usage, or outcomes | AIMeter OSS |
| Record audit evidence | AIAuditLog |
| Govern agent behavior | AgentPolicyPack |
| Define business meaning | OpenOntologyLite |
| Orchestrate agents | AgentForge |
| Run private/local AI infrastructure | PrivateAIStack |
| See the whole ecosystem pattern | Linux of AI Vendor Exit Demo |

## Recommended first demo

Start with the [Linux of AI Vendor Exit Demo](../examples/vendor-exit-demo/). The demo is deterministic, offline-first, and file-based. It demonstrates the integration pattern using portable files and reports, not deep runtime integration.

The demo now includes the same portable export pattern supported by
ModelSwapBench's AI Vendor Exit Report: an AIMeter OSS-style
`reports/aimeter_summary.json` file for cost/outcome measurement and an
AIAuditLog-style `audit/audit_events.jsonl` file for audit evidence.

## Install commands

```bash
pip install agentforge-oss
pip install privateaistack
pip install modelswapbench
pip install openontologylite
pip install agentpolicypack
pip install aiauditlog
pip install aimeter-oss
```

Python 3.11-3.13 is the intended supported range for the ecosystem.

## Project links

AgentForge:

- GitHub: https://github.com/sekacorn/AgentForge
- PyPI: https://pypi.org/project/agentforge-oss/

PrivateAIStack:

- GitHub: https://github.com/sekacorn/PrivateAIStack
- PyPI: https://pypi.org/project/privateaistack/

ModelSwapBench:

- GitHub: https://github.com/sekacorn/ModelSwapBench
- PyPI: https://pypi.org/project/modelswapbench/

OpenOntologyLite:

- GitHub: https://github.com/sekacorn/OpenOntologyLite
- PyPI: https://pypi.org/project/openontologylite/

AgentPolicyPack:

- GitHub: https://github.com/sekacorn/AgentPolicyPack
- PyPI: https://pypi.org/project/agentpolicypack/

AIAuditLog:

- GitHub: https://github.com/sekacorn/AIAuditLog
- PyPI: https://pypi.org/project/aiauditlog/

AIMeter OSS:

- GitHub: https://github.com/sekacorn/AIMeter
- PyPI: https://pypi.org/project/aimeter-oss/

## Important limitations

- Linux of AI is not a foundation model.
- It is not a hosted AI provider.
- It is not a compliance certification.
- It is not a legal guarantee.
- It does not prove a model migration is automatically safe.
- It does not replace human review in high-risk workflows.
- Estimated costs are not invoice-confirmed.
- Projected savings are not realized savings.
- Audit logs are tamper-evident patterns, not automatic legal non-repudiation.
