# hdbschedulerjob — HANA HDI Scheduler Job Artifact

## Overview
An `.hdbschedulerjob` file defines a **scheduled job** that executes a stored procedure on a cron-like schedule. Managed by the SAP HANA Job Scheduler service.

## File Extension
`.hdbschedulerjob`

## File Path in Container
`src/<JOB_NAME>.hdbschedulerjob`

## Syntax
```
SCHEDULER JOB "<Name>"
CRON '<cron_expression>'
ENABLE
PROCEDURE "<ProcedureName>"
[WITH PARAMETER ('<key>' = '<value>', ...)]
```

## CRON Expression Format
`second minute hour day month weekday year`

| Field | Values |
|-------|--------|
| second | 0-59 |
| minute | 0-59 |
| hour | 0-23 |
| day | 1-31 |
| month | 1-12 |
| weekday | 0-6 (0=Sunday) |
| year | YYYY or `*` |

Use `*` for "every" value.

## Examples

### Daily cleanup at midnight (every Monday)
```
SCHEDULER JOB "JOB_DAILY_CLEANUP"
CRON '* * * * 1 0 0'
ENABLE
PROCEDURE "PROC_CLEANUP_STAGING"
```

### Hourly cache refresh
```
SCHEDULER JOB "JOB_HOURLY_REFRESH"
CRON '* * * * * 0 0'
ENABLE
PROCEDURE "PROC_REFRESH_CACHE"
WITH PARAMETER ('batch_size' = '1000')
```

### Daily report at 6am
```
SCHEDULER JOB "JOB_DAILY_REPORT"
CRON '0 0 6 * * * *'
ENABLE
PROCEDURE "PROC_GENERATE_DAILY_REPORT"
```

### Weekly data archival (every Sunday at 2am)
```
SCHEDULER JOB "JOB_WEEKLY_ARCHIVE"
CRON '0 0 2 * * 0 *'
ENABLE
PROCEDURE "PROC_ARCHIVE_OLD_DATA"
```

## Rules
- Do **NOT** use `CREATE SCHEDULER JOB` — start directly with `SCHEDULER JOB`
- `ENABLE` activates the job immediately on deployment
- The procedure must be deployed in the **same container**
- Use `WITH PARAMETER` to pass key-value parameters to the procedure
- The procedure must accept no parameters OR only the parameters passed via `WITH PARAMETER`

## Monitoring Jobs
After deployment:
```sql
-- Check scheduled jobs
SELECT * FROM _SYS_TASK.M_SCHEDULER_JOBS
WHERE SCHEMA_NAME = 'AAK_CONTAINER';

-- Check job execution history
SELECT * FROM _SYS_TASK.M_SCHEDULER_JOB_LOG
WHERE SCHEMA_NAME = 'AAK_CONTAINER'
ORDER BY START_TIME DESC;
```

## Notes
- Requires the HANA Job Scheduler service to be enabled on the instance
- Jobs run in the context of the container's `#OO` user
- Deploy the procedure before the scheduler job
- To disable a job: redeploy with `DISABLE` instead of `ENABLE`