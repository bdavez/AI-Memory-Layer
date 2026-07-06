#!/bin/bash
echo "=== LOAD OPERATION ==="

latest=$(ls -1 .save | sort | tail -n 1)

if [ -z "$latest" ]; then
    echo "No SAVE snapshots found"
    exit 1
fi

echo "Loading snapshot: $latest"

cp -r .save/$latest/docs/inventory docs/
cp .save/$latest/spec.yaml compiler/spec.yaml

echo "LOAD complete"