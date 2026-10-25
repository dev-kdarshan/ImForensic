# Kafka design notes

Proposed topics: `analysis-jobs`, `engine-tasks`, `engine-results`, `analysis-status`, `analysis-errors`.

Use `analysis_id` as the message key where ordering within a partition is useful. If every engine must receive a task, use separate consumer groups or engine-specific task topics; consumers in one group share partitions. Make consumers idempotent, bound retries, and route exhausted failures to a dead-letter topic. Do not put image bytes in Kafka messages.
