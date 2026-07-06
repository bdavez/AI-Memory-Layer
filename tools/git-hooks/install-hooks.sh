#!/bin/bash

HOOKS_DIR="$(git rev-parse --git-dir)/hooks"

echo "Installing Git hooks into $HOOKS_DIR..."

cp tools/git-hooks/pre-commit "$HOOKS_DIR/pre-commit"
cp tools/git-hooks/post-merge "$HOOKS_DIR/post-merge"

chmod +x "$HOOKS_DIR/pre-commit"
chmod +x "$HOOKS_DIR/post-merge"

echo "✔ Git hooks installed."
