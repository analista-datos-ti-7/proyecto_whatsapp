# Inyección de dependencias
from __future__ import annotations
from config.settings import Settings
from src.whatsapp_metrics.domain.ports import SourceRepository, TargetRepository

class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._source: SourceRepository | None = None
        self._target: TargetRepository | None = None

    @property
    def source(self) -> SourceRepository:
        if self._source is None:
            from src.whatsapp_metrics.infrastructure.sqlserver.sagicc_repository import SagiccRepository
            self._source = SagiccRepository(self.settings.sqlserver)
        return self._source
    @property    
    def target(self) -> TargetRepository:
        if self._target is None:
            from src.whatsapp_metrics.infrastructure.localfiles.file_repository import LocalFileRepository
            self._target = LocalFileRepository(self.settings.etl.output_dir)
        return self._target