# hdbmigrationtable — HANA HDI Migration Table Artifact

## Overview
An `.hdbmigrationtable` file supports **schema evolution** (ADD/ALTER/RENAME COLUMN etc.) without dropping and recreating the table. Use this instead of `.hdbtable` for tables that already have data and need structural changes after initial deployment.

You write the explicit `ALTER TABLE` statements yourself — HDI does NOT auto-generate them.

## File Extension
`.hdbmigrationtable`

## File Path in Container
`src/<TABLE_NAME>.hdbmigrationtable`

## Syntax

```
== version = N
COLUMN TABLE "T" ( ... latest full structure ... )

== migration = 2
ALTER TABLE "T" ...;   -- steps to go from v1 to v2

== migration = 3
ALTER TABLE "T" ...;   -- steps to go from v2 to v3

...

== migration = N
ALTER TABLE "T" ...;   -- steps to go from v(N-1) to vN
```

**Important separator:** `== version` and `== migration` with spaces around the `=`.
NOT `===========` long lines. NOT the `MIGRATIONTABLE` keyword.

## Rules

1. File contains exactly **ONE** `== version = N` block — always the highest/latest version with the full current DDL.
2. Every migration step from `2` up to `N` must be present as `== migration = M` blocks.
3. **Initial deploy** (new container): creates the table directly from `== version = N`; migration blocks are ignored.
4. **Incremental deploy** (existing container at version k): runs `== migration = k+1` through `== migration = N` in order.
5. After all migrations run, the plug-in verifies the migrated table matches the `== version = N` definition.
6. `RENAME COLUMN` **IS supported** in migration steps.
7. **Supported ALTER ops:** ADD column, ALTER column type/length, RENAME column, ADD/DROP constraint, partitioning changes.
8. **NOT supported:** changing PRIMARY KEY columns, adding NOT NULL without DEFAULT on an existing table.
9. `development_mode=true` in build params causes ALL data to be lost — use only in dev containers.

## Examples

### Version 1 — Initial creation

```
== version = 1
COLUMN TABLE "PERSON"(
    "FIRSTNAME" NVARCHAR(100),
    "NAME"      NVARCHAR(100)
)
```

### Version 2 — Add columns + rename column

```
== version = 2
COLUMN TABLE "PERSON"(
    "FIRSTNAME" NVARCHAR(100),
    "LASTNAME"  NVARCHAR(100),
    "STREET"    NVARCHAR(100),
    "CITY"      NVARCHAR(100)
)

== migration = 2
ALTER TABLE "PERSON" ADD ("STREET" NVARCHAR(100));
ALTER TABLE "PERSON" ADD ("CITY"   NVARCHAR(100));
RENAME COLUMN "PERSON"."NAME" TO "LASTNAME";
```

### Version 3 — Alter column type + add column

```
== version = 3
COLUMN TABLE "PERSON"(
    "FIRSTNAME"   NVARCHAR(100),
    "LASTNAME"    NVARCHAR(100),
    "STREET"      NVARCHAR(200),
    "HOUSENUMBER" INTEGER,
    "CITY"        NVARCHAR(100)
)

== migration = 2
ALTER TABLE "PERSON" ADD ("STREET" NVARCHAR(100));
ALTER TABLE "PERSON" ADD ("CITY"   NVARCHAR(100));
RENAME COLUMN "PERSON"."NAME" TO "LASTNAME";

== migration = 3
ALTER TABLE "PERSON" ALTER ("STREET" NVARCHAR(200));
ALTER TABLE "PERSON" ADD ("HOUSENUMBER" INTEGER);
```

### General pattern for version N (N >= 2)

```
== version = N
COLUMN TABLE "T" ( ... most recent target structure ... )

== migration = 2
ALTER TABLE "T" ...;   -- v1 -> v2

== migration = 3
ALTER TABLE "T" ...;   -- v2 -> v3

...

== migration = N
ALTER TABLE "T" ...;   -- v(N-1) -> vN
```

## Supported Migration Operations

| Operation | Supported |
|-----------|-----------|
| ADD COLUMN | ✅ Yes |
| ALTER column type/length (widen) | ✅ Yes |
| RENAME COLUMN | ✅ Yes |
| ADD / DROP constraint | ✅ Yes |
| DROP COLUMN | ✅ Yes (data in that column is lost) |
| Change PRIMARY KEY | ❌ No |
| ADD NOT NULL column without DEFAULT on existing table | ❌ No |
| Narrow data type | ❌ No |

## Key Differences from .hdbtable

| | `.hdbtable` | `.hdbmigrationtable` |
|---|---|---|
| Schema evolution | Drops + recreates table (data lost) | ALTER TABLE — data preserved |
| You write ALTER? | No | **Yes — explicitly required** |
| Migration steps | None | `== migration = M` blocks |
| Version tracking | None | `== version = N` block |
| Use for | New tables / dev | Production tables with data |

## Notes

- Use for **production tables** that already contain data
- You must write all `ALTER TABLE` statements manually in each `== migration = M` block
- HDI does NOT auto-generate ALTER statements — that is `.hdbmigrationtable`'s key difference vs the old `MIGRATIONTABLE` keyword (which is now deprecated)
- For staging/temp tables where data loss is acceptable, use `.hdbdropcreatetable` instead
- For brand-new tables with no data, `.hdbtable` is simpler