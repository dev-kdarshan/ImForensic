#!/usr/bin/env bash
set -euo pipefail
BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
for topic in analysis-jobs engine-tasks engine-results analysis-status analysis-errors; do
  docker run --rm --network host apache/kafka:latest \
    /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" \
    --create --if-not-exists --topic "$topic" --partitions 3 --replication-factor 1
done
