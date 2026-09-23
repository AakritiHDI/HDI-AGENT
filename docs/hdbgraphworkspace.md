# hdbgraphworkspace — HANA HDI Graph Workspace Artifact

## Overview
An `.hdbgraphworkspace` file defines a **graph workspace** that binds edge and vertex tables for SAP HANA Graph algorithms (shortest path, neighbors, connected components, etc.).

## File Extension
`.hdbgraphworkspace`

## File Path in Container
`src/<WORKSPACE_NAME>.hdbgraphworkspace`

## Syntax
```
GRAPH WORKSPACE "<Name>"
EDGE TABLE   "<EdgeTable>"   SOURCE COLUMN "<src_col>" TARGET COLUMN "<tgt_col>" KEY COLUMN "<key_col>"
VERTEX TABLE "<VertexTable>" KEY COLUMN "<key_col>"
```

## Rules
- Do **NOT** use `CREATE GRAPH WORKSPACE` — start directly with `GRAPH WORKSPACE`
- Edge table requires: SOURCE COLUMN, TARGET COLUMN, KEY COLUMN
- Vertex table requires: KEY COLUMN
- The same table can serve as both edge and vertex (self-referencing graph)
- Both edge and vertex tables must be deployed in the same container

## Examples

### Social network graph
```
GRAPH WORKSPACE "WS_GRAPH"
EDGE TABLE   "RELATIONSHIPS" SOURCE COLUMN "SOURCE_ID" TARGET COLUMN "TARGET_ID" KEY COLUMN "EDGE_ID"
VERTEX TABLE "MEMBERS"       KEY COLUMN "MEMBER_ID"
```

### Organizational hierarchy (self-referencing)
```
GRAPH WORKSPACE "WS_ORG"
EDGE TABLE   "EMPLOYEE" SOURCE COLUMN "ID" TARGET COLUMN "MANAGERID" KEY COLUMN "ID"
VERTEX TABLE "EMPLOYEE" KEY COLUMN "ID"
```

### Road network graph
```
GRAPH WORKSPACE "WS_ROADS"
EDGE TABLE   "ROADS"       SOURCE COLUMN "FROM_NODE" TARGET COLUMN "TO_NODE" KEY COLUMN "ROAD_ID"
VERTEX TABLE "INTERSECTIONS" KEY COLUMN "NODE_ID"
```

## Required Table Structure

### Edge table minimum columns
```
COLUMN TABLE "RELATIONSHIPS" (
    "EDGE_ID"   INTEGER NOT NULL,
    "SOURCE_ID" INTEGER NOT NULL,
    "TARGET_ID" INTEGER NOT NULL,
    PRIMARY KEY ("EDGE_ID")
)
```

### Vertex table minimum columns
```
COLUMN TABLE "MEMBERS" (
    "MEMBER_ID" INTEGER NOT NULL,
    "NAME"      NVARCHAR(100),
    PRIMARY KEY ("MEMBER_ID")
)
```

## Using Graph Algorithms
After deployment, run graph algorithms via SQL:
```sql
-- Shortest path between two vertices
SELECT * FROM GRAPH_ALGORITHM_SHORTEST_PATH(
    WORKSPACE => 'AAK_CONTAINER.WS_GRAPH',
    SOURCE => 1,
    TARGET => 5
);
```

## Notes
- Deploy the graph workspace **after** all referenced tables are deployed
- Graph workspaces work with SAP HANA Cloud's built-in graph engine
- Supported algorithms: SHORTEST_PATH, NEIGHBORS, CONNECTED_COMPONENTS, BFS, DFS