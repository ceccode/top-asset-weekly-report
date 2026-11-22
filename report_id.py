"""Identity of a report: its date and scope, and every name derived from them."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

SCOPES = ("global", "software")
DATE_FORMAT = "%Y-%m-%d"

_LABELS = {"global": "Global Assets", "software": "Software Companies"}


@dataclass(frozen=True)
class ReportId:
    date: str
    scope: str

    @classmethod
    def from_path(cls, path: Path) -> Optional["ReportId"]:
        """Parse a `<date>.<scope>.<ext>` file name; None when it is not a report's."""
        parts = path.name.split(".")
        if len(parts) < 3:
            return None
        try:
            datetime.strptime(parts[0], DATE_FORMAT)
        except ValueError:
            return None
        return cls(parts[0], parts[1])

    @property
    def stem(self) -> str:
        return f"{self.date}.{self.scope}"

    @property
    def label(self) -> str:
        """What the report covers, as shown in titles."""
        return _LABELS.get(self.scope, _LABELS["software"])

    @property
    def title(self) -> str:
        return f"{self.label} Weekly Report - {self.date}"

    @property
    def markdown_name(self) -> str:
        return f"{self.stem}.md"

    @property
    def csv_name(self) -> str:
        return f"{self.stem}.csv"

    @property
    def json_name(self) -> str:
        return f"{self.stem}.json"

    @property
    def telegram_snapshot_name(self) -> str:
        """Name of the Telegram text next to the snapshots."""
        return f"{self.date}.telegram.{self.scope}.txt"

    @property
    def telegram_public_name(self) -> str:
        """Name of the Telegram text once published."""
        return f"{self.stem}.txt"
