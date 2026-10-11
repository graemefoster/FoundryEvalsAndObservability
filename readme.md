# Agent Evaluation Demo

A presentation and runnable sample exploring agent evaluation, observability
and optimisation with Microsoft Foundry and Microsoft Agent Framework.

**Model choice -> grounding -> traces -> evaluation -> optimisation -> CI/CD**

The sample agent answers purchasing questions using fictional policies, a workplace
directory and a department budget. Its three read-only tools are local stand-ins for
Foundry IQ, Work IQ and Fabric IQ; they don't connect to the real services.

## Start here

- [Playbook](PLAYBOOK.md): demo walkthrough, prerequisites, setup and run commands.
- Presentation: [HTML deck](presentation/deck.html) or [PowerPoint](presentation/presentation.pptx).
- [Sample](sample/): agent, evaluation datasets, judges and Azure configuration.

Azure hosting, model calls and telemetry can incur charges. Follow the playbook
before deploying or starting evaluation and optimisation runs.
