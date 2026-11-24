#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../os_module"
make
exec ./campusresos_worker
