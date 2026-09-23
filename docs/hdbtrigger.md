# hdbtrigger — HANA HDI Trigger Artifact

## Overview
An `.hdbtrigger` file defines a **BEFORE/AFTER INSERT/UPDATE/DELETE trigger** on a table as a design-time artifact in an HDI container.

## File Extension
`.hdbtrigger`

## File Path in Container
`src/<TRIGGER_NAME>.hdbtrigger`

## Syntax
```
TRIGGER "<Name>"
BEFORE|AFTER INSERT|UPDATE|DELETE [OR INSERT|UPDATE|DELETE ...]
ON "<TableName>"
[REFERENCING NEW ROW AS NEW_ROW, OLD ROW AS OLD_ROW]
FOR EACH ROW
BEGIN
    -- body
END
```

## Rules
- Do **NOT** use `CREATE TRIGGER` — start directly with `TRIGGER`
- Use `::TRIGGER_INSERT_EVENT`, `::TRIGGER_UPDATE_EVENT`, `::TRIGGER_DELETE_EVENT` system variables to distinguish event type in a combined trigger
- Reference new/old row values with `:NEW_ROW.<col>` and `:OLD_ROW.<col>`
- BEFORE triggers can modify values before they are written

## Examples

### Combined INSERT/UPDATE/DELETE trigger with event check
```
TRIGGER "SVT_TRIGGER"
BEFORE INSERT OR UPDATE OR DELETE ON "TYPES"
REFERENCING NEW ROW AS NEW_ROW, OLD ROW AS OLD_ROW
FOR EACH ROW
BEGIN
    IF ::TRIGGER_INSERT_EVENT = TRUE THEN
        INSERT INTO "TRIG_TYPES"(ID, COUNTRY, BOOLEAN_VAL)
        VALUES(:NEW_ROW.ID, :NEW_ROW.COUNTRY, :NEW_ROW.BOOLEAN_VAL);
    ELSEIF ::TRIGGER_UPDATE_EVENT = TRUE THEN
        UPDATE "TRIG_TYPES"
        SET BOOLEAN_VAL = :NEW_ROW.BOOLEAN_VAL
        WHERE ID = :NEW_ROW.ID;
    ELSE
        DELETE FROM "TRIG_TYPES" WHERE ID = :OLD_ROW.ID;
    END IF;
END
```

### AFTER INSERT audit trigger
```
TRIGGER "AUDIT_INSERT"
AFTER INSERT ON "COURSES"
REFERENCING NEW ROW AS NEW_ROW
FOR EACH ROW
BEGIN
    INSERT INTO "AUDIT_LOG"(TABLE_NAME, ACTION, RECORD_ID, CHANGED_AT)
    VALUES('COURSES', 'INSERT', :NEW_ROW.COURSEID, CURRENT_TIMESTAMP);
END
```

### BEFORE INSERT default value trigger
```
TRIGGER "DEFAULT_REGION"
BEFORE INSERT ON "SALES"
REFERENCING NEW ROW AS NEW_ROW
FOR EACH ROW
BEGIN
    IF :NEW_ROW.REGION IS NULL THEN
        NEW_ROW.REGION := 'UNKNOWN';
    END IF;
END
```

## Notes
- The table being triggered on must be deployed in the same container
- Trigger and its table must be deployed together (include both in DI.MAKE paths)
- For combined triggers, use `OR` between event types: `INSERT OR UPDATE OR DELETE`