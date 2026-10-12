"""
Concurrent batch invoice processor for processing thousands of invoices.
"""

import concurrent.futures
import csv
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

from nesy_docai.pipeline import NeSyInvoicePipeline
from nesy_docai.csv_exporter import InvoiceCSVExporter
from nesy_docai.config import NeSyConfig
from nesy_docai.logging_setup import get_logger

logger = get_logger(__name__)

@dataclass
class BatchResult:
    total_files: int
    successful: int
    failed: int
    skipped: int
    output_csv: Path
    error_log: Path
    elapsed_seconds: float


def _process_single_file(filepath: str) -> Dict[str, Any]:
    """Module-level function for multiprocessing pickle compatibility."""
    try:
        pipeline = NeSyInvoicePipeline()
        result = pipeline.process_file(filepath)
        return {"filepath": filepath, "status": "success", "data": result}
    except Exception as e:
        return {"filepath": filepath, "status": "error", "error_message": str(e)}


class BatchInvoiceProcessor:
    def __init__(self, config: Optional[NeSyConfig] = None):
        self.config = config or NeSyConfig()

    def process_directory(self, input_dir: Path, output_csv: Path, resume: bool = False) -> BatchResult:
        start_time = time.time()
        
        supported_extensions = {".png", ".jpg", ".jpeg", ".pdf"}
        all_files = [
            f for f in input_dir.iterdir()
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]
        
        checkpoint_path = output_csv.parent / f"{output_csv.stem}.checkpoint"
        error_log_path = output_csv.parent / f"{output_csv.stem}_errors.csv"
        
        processed_files = set()
        if resume and checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                processed_files = set(f.read().splitlines())
        
        files_to_process = [f for f in all_files if f.name not in processed_files]
        skipped = len(all_files) - len(files_to_process)
        
        successful = 0
        failed = 0
        results_data = []
        error_data = []
        
        logger.info(f"Starting batch processing: {len(all_files)} total files, {skipped} skipped, {len(files_to_process)} to process.")
        
        max_workers = getattr(self.config, 'max_workers', 4)
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(_process_single_file, str(f)): f 
                for f in files_to_process
            }
            
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_file):
                f = future_to_file[future]
                completed_count += 1
                
                try:
                    result = future.result()
                    if result["status"] == "success":
                        successful += 1
                        results_data.append(result["data"])
                    else:
                        failed += 1
                        error_data.append({
                            "filename": f.name,
                            "error_message": result["error_message"],
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
                        })
                except Exception as e:
                    failed += 1
                    error_data.append({
                        "filename": f.name,
                        "error_message": f"Worker crashed: {str(e)}",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
                    })
                
                # Checkpoint
                with open(checkpoint_path, 'a', encoding='utf-8') as cp_file:
                    cp_file.write(f"{f.name}\n")
                
                # Progress tracking
                if completed_count % 10 == 0 or completed_count == len(files_to_process):
                    percent = (completed_count / len(files_to_process)) * 100
                    logger.info(f"Progress: {completed_count}/{len(files_to_process)} files processed ({percent:.1f}%)")

        # Write to CSV
        if results_data:
            exporter = InvoiceCSVExporter()
            exporter.export(results_data, str(output_csv))
                
        # Write error log
        if error_data:
            file_mode = 'a' if resume and error_log_path.exists() else 'w'
            with open(error_log_path, file_mode, encoding='utf-8-sig', newline='') as ef:
                writer = csv.DictWriter(ef, fieldnames=["filename", "error_message", "timestamp"])
                if file_mode == 'w':
                    writer.writeheader()
                writer.writerows(error_data)

        elapsed_seconds = time.time() - start_time
        
        return BatchResult(
            total_files=len(all_files),
            successful=successful,
            failed=failed,
            skipped=skipped,
            output_csv=output_csv,
            error_log=error_log_path,
            elapsed_seconds=elapsed_seconds
        )

    def process_zip(self, zip_path: Path, output_csv: Path) -> BatchResult:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)
            
            logger.info(f"Extracted {zip_path.name} to temporary directory. Starting batch process...")
            result = self.process_directory(temp_path, output_csv, resume=False)
            
        return result
