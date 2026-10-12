"""NeSy-DocAI CLI — Production Invoice Processing Tool"""

import argparse
import logging
import sys
import time
from pathlib import Path

from nesy_docai import __version__
from nesy_docai.pipeline import NeSyInvoicePipeline
from nesy_docai.batch_processor import BatchInvoiceProcessor, BatchResult
from nesy_docai.config import NeSyConfig
from nesy_docai.csv_exporter import InvoiceCSVExporter


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    parser = argparse.ArgumentParser(description="NeSy-DocAI CLI \u2014 Production Invoice Processing Tool")
    parser.add_argument("input", type=str, help="Path to invoice file, directory, or ZIP archive")
    parser.add_argument("-o", "--output", type=str, default="output.csv", help="Output file path (default: 'output.csv')")
    parser.add_argument("-f", "--format", choices=["csv", "xlsx", "json"], default="csv", help="Output format (default='csv')")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--config", type=str, help="Optional config YAML/JSON file path")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose/debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        sys.exit(1)

    config = NeSyConfig()
    if args.config:
        config.load(args.config)
    config.max_workers = args.workers

    try:
        if input_path.is_file() and input_path.suffix.lower() == ".zip":
            logger.info(f"Processing ZIP file: {input_path}")
            processor = BatchInvoiceProcessor(config=config)
            result = processor.process_zip(input_path, output_path)
            
            logger.info("Batch Processing Summary:")
            logger.info(f"Total files: {result.total_files}")
            logger.info(f"Successful: {result.successful}")
            logger.info(f"Failed: {result.failed}")
            logger.info(f"Skipped: {result.skipped}")
            logger.info(f"Elapsed time: {result.elapsed_seconds:.2f} seconds")
            logger.info(f"Output path: {result.output_csv}")

        elif input_path.is_dir():
            logger.info(f"Processing directory: {input_path}")
            processor = BatchInvoiceProcessor(config=config)
            result = processor.process_directory(input_path, output_path, resume=args.resume)

            logger.info("Batch Processing Summary:")
            logger.info(f"Total files: {result.total_files}")
            logger.info(f"Successful: {result.successful}")
            logger.info(f"Failed: {result.failed}")
            logger.info(f"Skipped: {result.skipped}")
            logger.info(f"Elapsed time: {result.elapsed_seconds:.2f} seconds")
            logger.info(f"Output path: {result.output_csv}")

        else:
            supported_extensions = {".png", ".jpg", ".jpeg", ".pdf"}
            if input_path.suffix.lower() not in supported_extensions:
                logger.error(f"Unsupported file type: {input_path.suffix}")
                sys.exit(1)
                
            logger.info(f"Processing single file: {input_path}")
            start_time = time.time()
            pipeline = NeSyInvoicePipeline()
            data = pipeline.process_file(str(input_path))
            
            if args.format == "csv":
                exporter = InvoiceCSVExporter()
                exporter.export([data], str(output_path))
            elif args.format == "json":
                import json
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump([data], f, ensure_ascii=False, indent=2)
            else:
                logger.warning(f"Format {args.format} not fully implemented in this example CLI.")
                
            elapsed_time = time.time() - start_time
            logger.info("Processing Summary:")
            logger.info(f"Total files: 1")
            logger.info(f"Successful: 1")
            logger.info(f"Failed: 0")
            logger.info(f"Skipped: 0")
            logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
            logger.info(f"Output path: {output_path}")

    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error during processing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
