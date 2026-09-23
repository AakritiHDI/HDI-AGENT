# HANA HDI Agent 🤖

An AI agent for creating, deploying and managing **SAP HANA HDI design-time artifacts**
via HANA's SQL API — powered by **SAP AI Core / GenAI Hub** (same as HANA-TEA).

---

## What it does

You describe what you need in plain English. The agent:
1. Reads the artifact reference docs from `docs/`
2. Generates correct HDI artifact syntax
3. Writes the file into your HDI container via `_SYS_DI` SQL API
4. Deploys it via HDI MAKE

### Example prompts
```
Create an hdbtable called EMPLOYEES with ID, name, email, hire date and salary
Create an hdbview that joins EMPLOYEES with DEPARTMENTS
Create an hdbprocedure to insert a new employee
List all artifacts in my container
Drop the EMPLOYEES table
```

---

## Project Structure

```
hdi-agent/
├── main.py                    ← CLI entry point
├── pyproject.toml
├── .env.example               ← copy to .env and fill credentials
├── config/
│   └── default.yaml           ← model + hana config
├── agent/
│   ├── __init__.py
│   ├── agent.py               ← core agentic loop (gen_ai_hub Bedrock)
│   ├── hana_client.py         ← HANA connection + HDI SQL API
│   ├── llm.py                 ← SAP AI Core / gen_ai_hub provider
│   └── tools.py               ← all 7 tool definitions + handlers
├── docs/                      ← reference docs the agent reads
│   ├── hdbtable.md
│   ├── hdbview.md
│   ├── hdbprocedure.md
│   ├── hdbsequence.md
│   ├── hdbsynonym.md
│   └── hdbindex.md
└── mcp_server/
    └── server.py              ← MCP server for Cline / Claude Desktop
```

---

## Setup

### 1. Install dependencies
```bash
pip install -e .
```
Or manually:
```bash
pip install hdbcli generative-ai-hub-sdk python-dotenv rich click requests mcp
```

### 2. Configure credentials
```bash
cp .env.example .env
# Edit .env — fill in HANA_* and AICORE_* values
```

### 3. Run
```bash
# Interactive chat
python main.py

# Single prompt
python main.py --prompt "Create an hdbtable called PRODUCTS with SKU, name, price"

# With default container
python main.py --container MY_CONTAINER
```

---

## MCP Server (Cline / Claude Desktop)
```bash
python mcp_server/server.py
```
Add to `cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "hdi-agent": {
      "command": "python",
      "args": ["/absolute/path/to/hdi-agent/mcp_server/server.py"]
    }
  }
}
```

---

## Architecture

```
User Prompt
    │
    ▼
HDIAgent.chat()
    │
    ├─► converse_stream()  ←──── SAP AI Core (gen_ai_hub Bedrock client)
    │         │
    │    stopReason == "tool_use"
    │         │
    │    dispatch(tool_name, args)
    │         │
    │         ├─► read_artifact_doc   → reads docs/*.md
    │         ├─► create_artifact_file→ HANAClient.hdi_write_file()
    │         ├─► deploy_artifact     → HANAClient.hdi_make()
    │         ├─► list_artifacts      → _SYS_DI#<C>.M_FILES
    │         ├─► drop_artifact       → HANAClient.hdi_drop_file()
    │         ├─► execute_sql         → HANAClient.execute()
    │         └─► list_containers     → _SYS_DI.M_ALL_CONTAINERS
    │
    └─► stopReason == "end_turn"  →  Final Answer
```

---

## Supported Artifact Types

| Artifact | Extension | Reference Doc |
|----------|-----------|---------------|
| Column Table | `.hdbtable` | `docs/hdbtable.md` |
| Migration Table | `.hdbmigrationtable` | `docs/hdbmigrationtable.md` |
| View | `.hdbview` | `docs/hdbview.md` |
| Calculation View | `.hdbcalculationview` | `docs/hdbcalculationview.md` |
| Projection View | `.hdbprojectionview` | `docs/hdbprojectionview.md` |
| Stored Procedure | `.hdbprocedure` | `docs/hdbprocedure.md` |
| Function | `.hdbfunction` | `docs/hdbfunction.md` |
| Trigger | `.hdbtrigger` | `docs/hdbtrigger.md` |
| Index | `.hdbindex` | `docs/hdbindex.md` |
| Table Type | `.hdbtabletype` | `docs/hdbtabletype.md` |
| Synonym | `.hdbsynonym` | `docs/hdbsynonym.md` |
| Synonym Config | `.hdbsynonymconfig` | `docs/hdbsynonymconfig.md` |
| Role | `.hdbrole` | `docs/hdbrole.md` |
| Grants | `.hdbgrants` | `docs/hdbgrants.md` |
| Structured Privilege | `.hdbstructuredprivilege` | `docs/hdbstructuredprivilege.md` |
| Analytic Privilege | `.hdbanalyticprivilege` | `docs/hdbanalyticprivilege.md` |
| Virtual Table | `.hdbvirtualtable` | `docs/hdbvirtualtable.md` |
| SQLScript Library | `.hdblibrary` | `docs/hdblibrary.md` |
| Graph Workspace | `.hdbgraphworkspace` | `docs/hdbgraphworkspace.md` |
| Scheduler Job | `.hdbschedulerjob` | `docs/hdbschedulerjob.md` |
| Logical Schema | `.hdblogicalschema` | `docs/hdblogicalschema.md` |
| Application Time | `.hdbapplicationtime` | `docs/hdbapplicationtime.md` |
| System Versioning | `.hdbsystemversioning` | `docs/hdbsystemversioning.md` |