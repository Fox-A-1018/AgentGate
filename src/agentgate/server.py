from __future__ import annotations

import os
from pathlib import Path

from agentgate.api import create_api
from agentgate.application import build_application


PROJECT_ROOT = Path(os.environ.get("AGENTGATE_PROJECT_ROOT", Path.cwd())).resolve()
app = create_api(build_application(PROJECT_ROOT))

