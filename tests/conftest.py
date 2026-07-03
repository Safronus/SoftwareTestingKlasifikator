"""Sdílená pytest konfigurace.

Qt GUI testy (delegáti, model) běží offscreen — nevytvářejí viditelné okno
a fungují i bez displeje (CI). `setdefault` nechá případné explicitní
nastavení uživatele nedotčené.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
