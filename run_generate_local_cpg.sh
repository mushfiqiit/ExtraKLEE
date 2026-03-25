#!/usr/bin/env bash
set -euo pipefail

# Beginner-friendly helper script for running GenerateLocalCpg.
# It compiles the Scala file and then runs it.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

scalac generate_cpg.scala
scala GenerateLocalCpg