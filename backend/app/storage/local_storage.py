import os
import uuid
from pathlib import Path
from typing import Tuple
from backend.app.core.config import settings

class LocalStorageService:
    def __init__(self, base_path: str = None, report_path: str = None):
        self.base_path = Path(base_path or settings.STORAGE_BASE_PATH).resolve()
        self.report_path = Path(report_path or settings.REPORT_STORAGE_PATH).resolve()
        
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.report_path.mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, original_filename: str) -> Tuple[str, str, int]:
        ext = Path(original_filename).suffix.lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        destination = self.base_path / unique_name
        
        with open(destination, "wb") as f:
            f.write(content)
            
        file_size = len(content)
        relative_path = f"uploads/{unique_name}"
        return relative_path, str(destination), file_size

    def save_report(self, content: bytes, filename: str) -> Tuple[str, str]:
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        destination = self.report_path / unique_name
        
        with open(destination, "wb") as f:
            f.write(content)
            
        relative_path = f"reports/{unique_name}"
        return relative_path, str(destination)

    def get_absolute_path(self, relative_path: str) -> Path:
        if relative_path.startswith("uploads/"):
            filename = relative_path.replace("uploads/", "")
            return self.base_path / filename
        elif relative_path.startswith("reports/"):
            filename = relative_path.replace("reports/", "")
            return self.report_path / filename
        return Path(relative_path).resolve()

    def delete_file(self, relative_path: str) -> bool:
        try:
            target = self.get_absolute_path(relative_path)
            if target.exists():
                os.remove(target)
                return True
        except Exception:
            pass
        return False

storage_service = LocalStorageService()
