# hdbconstraint — HANA HDI Referential Constraint Artifact

## Overview
An `.hdbconstraint` file defines a **foreign key constraint** on a table as a design-time artifact in an HDI container.

## File Extension
`.hdbconstraint`

## File Path in Container
`src/<CONSTRAINT_NAME>.hdbconstraint`

## Syntax
```
CONSTRAINT "<Name>"
ON "<TableName>"
FOREIGN KEY (<col>) REFERENCES "<ReferencedTable>" (<col>)
[ON UPDATE CASCADE|SET NULL|RESTRICT]
[ON DELETE CASCADE|SET NULL|RESTRICT]
```

## Rules
- Do **NOT** use `ALTER TABLE ... ADD CONSTRAINT` — start directly with `CONSTRAINT`
- The constraint is a **separate artifact** from the table definition
- Both the table and the referenced table must be deployed in the same container
- The foreign key column(s) must match the data type of the referenced column(s)

## Examples

### Self-referencing foreign key with CASCADE
```
CONSTRAINT "EMPLOYEE_FK"
ON "EMPLOYEE"
FOREIGN KEY (MANAGERID) REFERENCES "EMPLOYEE" (ID) ON UPDATE CASCADE
```

### Cross-table foreign key with SET NULL on delete
```
CONSTRAINT "COURSES_INSTRUCTOR_FK"
ON "COURSES"
FOREIGN KEY (INSTRUCTORID) REFERENCES "INSTRUCTOR" (INSTRUCTORID)
ON DELETE SET NULL
```

### Simple foreign key (no action on update/delete)
```
CONSTRAINT "ORDER_CUSTOMER_FK"
ON "ORDERS"
FOREIGN KEY (CUSTOMER_ID) REFERENCES "CUSTOMERS" (CUSTOMER_ID)
```

### Composite foreign key
```
CONSTRAINT "ORDER_ITEM_FK"
ON "ORDER_ITEMS"
FOREIGN KEY (ORDER_ID, LINE_NO) REFERENCES "ORDERS" (ORDER_ID, LINE_NO)
ON DELETE CASCADE
```

## Referential Actions

| Action | Description |
|--------|-------------|
| `CASCADE` | Propagate UPDATE/DELETE to child rows |
| `SET NULL` | Set FK column to NULL when parent row deleted |
| `RESTRICT` | Block DELETE/UPDATE if child rows exist (default) |

## Notes
- Deploy the constraint **after** both tables are deployed (or together)
- The referenced column must be a PRIMARY KEY or have a UNIQUE constraint
- To drop a constraint: use `drop_artifact` with `file_path = "src/<CONSTRAINT_NAME>.hdbconstraint"`