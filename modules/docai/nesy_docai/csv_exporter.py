import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

# Assuming this function exists in the project
from nesy_docai.tax_code_mapper import infer_tax_code

logger = logging.getLogger(__name__)

class InvoiceCSVExporter:
    """Exporter for saving invoice records to CSV format compatible with Excel and Vietnamese characters."""
    
    REQUIRED_COLUMNS = [
        'Mã số thuế NB',
        'Nội dung diễn giải',
        'Thuế suất (%)',
        'Tiền thuế GTGT',
        'Mã thuế suất'
    ]
    
    OPTIONAL_COLUMNS = [
        'STT',
        'Số hóa đơn',
        'Ngày hóa đơn',
        'Tên người bán',
        'Tiền hàng chưa thuế',
        'Tổng thanh toán',
        'Trạng thái',
        'Độ tin cậy',
        'File gốc'
    ]

    def export(
        self,
        records: List[Dict[str, Any]],
        output_path: Path,
        encoding: str = 'utf-8-sig',
        include_optional: bool = True
    ) -> Path:
        """
        Export a list of invoice records to a CSV file.
        
        Args:
            records: List of dictionaries containing invoice data.
            output_path: The path where the CSV should be saved.
            encoding: Text encoding to use (utf-8-sig recommended for Excel).
            include_optional: Whether to include optional columns.
            
        Returns:
            The path to the generated CSV file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = list(self.REQUIRED_COLUMNS)
        if include_optional:
            fieldnames.extend(self.OPTIONAL_COLUMNS)
            
        try:
            with open(output_path, mode='w', encoding=encoding, newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                
                for idx, record in enumerate(records, start=1):
                    row = self._prepare_row(record, idx, include_optional)
                    writer.writerow(row)
                    
            logger.info(f"Successfully exported {len(records)} records to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error exporting CSV to {output_path}: {e}")
            raise

    def export_batch_summary(
        self,
        results: List[Dict[str, Any]],
        output_path: Path
    ) -> Path:
        """
        Export a batch summary highlighting errors and skipped records.
        
        Args:
            results: List of batch processing result dictionaries.
            output_path: The path where the summary CSV should be saved.
            
        Returns:
            The path to the generated summary CSV file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = [
            'File Name',
            'Status',
            'Error Message',
            'Processing Time (s)'
        ]
        
        try:
            with open(output_path, mode='w', encoding='utf-8-sig', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    writer.writerow({
                        'File Name': result.get('filename', ''),
                        'Status': result.get('status', 'UNKNOWN'),
                        'Error Message': result.get('error', ''),
                        'Processing Time (s)': result.get('processing_time', '')
                    })
                    
            logger.info(f"Successfully exported batch summary to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error exporting batch summary to {output_path}: {e}")
            raise

    def _prepare_row(
        self,
        record: Dict[str, Any],
        row_idx: int,
        include_optional: bool
    ) -> Dict[str, Any]:
        """Prepare a single record dictionary for CSV writing."""
        row = {}
        
        # Determine Description
        description = record.get('description_summary', '')
        if not description and 'line_items' in record and isinstance(record['line_items'], list):
            descriptions = [
                item.get('description', '') 
                for item in record['line_items'] 
                if isinstance(item, dict) and item.get('description')
            ]
            description = '; '.join(descriptions)
            
        # Determine Tax Rate & Amount
        # Pipeline stores tax_rate as "10%" or numeric, and tax amount as "tax"
        tax_rate = record.get('tax_rate', '')
        tax_amount = record.get('tax', record.get('tax_amount', ''))
        
        # Clean tax_rate to numeric for mapping (remove '%' suffix)
        tax_rate_numeric = None
        if tax_rate and tax_rate != 'N/A':
            try:
                rate_str = str(tax_rate).replace('%', '').strip()
                tax_rate_numeric = float(rate_str)
            except (ValueError, TypeError):
                pass

        # Determine subtotal for tax code inference
        subtotal = None
        try:
            sub_val = record.get('subtotal')
            if sub_val is not None and str(sub_val).strip():
                subtotal = int(str(sub_val).replace(',', '').replace('.', '').strip())
        except (ValueError, TypeError):
            pass

        tax_amt_int = None
        try:
            if tax_amount is not None and str(tax_amount).strip():
                tax_amt_int = int(str(tax_amount).replace(',', '').replace('.', '').strip())
        except (ValueError, TypeError):
            pass

        # Map Tax Code using infer_tax_code
        vendor_tax_code = ''
        try:
            vendor_tax_code = infer_tax_code(
                tax_rate_percent=tax_rate_numeric,
                subtotal=subtotal,
                tax_amount=tax_amt_int
            )
        except Exception:
            # Fallback logic mapping
            if tax_rate_numeric is not None:
                rate_int = int(tax_rate_numeric)
                if rate_int in (0, 5, 8, 10):
                    vendor_tax_code = str(rate_int)
        
        # Map REQUIRED columns
        row['Mã số thuế NB'] = record.get('seller_tax_id', '')
        row['Nội dung diễn giải'] = description
        row['Thuế suất (%)'] = tax_rate
        row['Tiền thuế GTGT'] = tax_amount
        row['Mã thuế suất'] = vendor_tax_code
        
        # Map OPTIONAL columns
        if include_optional:
            row['STT'] = row_idx
            row['Số hóa đơn'] = record.get('invoice_id', '')
            row['Ngày hóa đơn'] = record.get('invoice_date', '')
            row['Tên người bán'] = record.get('seller_name', '')
            row['Tiền hàng chưa thuế'] = record.get('subtotal', '')
            row['Tổng thanh toán'] = record.get('total', '')
            row['Trạng thái'] = record.get('audit_status', record.get('status', ''))
            row['Độ tin cậy'] = record.get('confidence_score', record.get('confidence', ''))
            row['File gốc'] = record.get('file_name', record.get('source_file', ''))
            
        return row

