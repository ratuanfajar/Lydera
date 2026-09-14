import logging
import shutil
from pathlib import Path
from app.core.taskiq import broker  

logger = logging.getLogger(__name__)


@broker.task
async def cleanup_module_files_task(file_paths: list[tuple[str | None, str | None]]) -> None:
    """Taskiq worker task to clean up files and directories off the web server."""
    for pdf_path, out_dir in file_paths:
        if pdf_path:
            try:
                Path(pdf_path).unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed deleting PDF {pdf_path}: {e}")

        if out_dir:
            try:
                shutil.rmtree(out_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"Failed deleting directory {out_dir}: {e}")