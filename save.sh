#!/bin/bash
echo "=== SAVE OPERATION (STRICT) ==="

# Validate before saving
python3 compiler/validate.py
if [ $? -ne 0 ]; then
    echo "SAVE aborted: validation failed"
    exit 1
fi

timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
mkdir -p .save/$timestamp

cp -r docs/inventory .save/$timestamp/
cp compiler/spec.yaml .save/$timestamp/

echo "SAVE complete: $timestamp"