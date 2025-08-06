import pandas as pd
import logging
from typing import Dict, List, Any
from config import config
import os

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

def validate_excel_file(file_path: str) -> None:
    """
    Validate Excel file structure and content
    
    Args:
        file_path: Path to the Excel file
        
    Raises:
        ValidationError: If file is invalid
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise ValidationError(f"File does not exist: {file_path}")
        
        # Try to read Excel file
        xl = pd.ExcelFile(file_path)
        
        # Check if file has any sheets
        if not xl.sheet_names:
            raise ValidationError("Excel file has no sheets")
            
        # Check each sheet
        for sheet_name in xl.sheet_names:
            validate_excel_sheet(xl, sheet_name)
            
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(f"Invalid Excel file: {str(e)}")

def validate_excel_sheet(xl: pd.ExcelFile, sheet_name: str) -> None:
    """
    Validate individual Excel sheet structure
    
    Args:
        xl: ExcelFile object
        sheet_name: Name of the sheet to validate
        
    Raises:
        ValidationError: If sheet is invalid
    """
    try:
        df = xl.parse(sheet_name, header=None)
        
        # Check if sheet is empty
        if df.empty:
            raise ValidationError(f"Sheet '{sheet_name}' is empty")
        
        # Check minimum required columns
        if len(df.columns) < 5:
            raise ValidationError(f"Sheet '{sheet_name}' must have at least 5 columns")
        
        # Check minimum required rows
        if len(df) < config.EXCEL_CONFIG['DATA_START_ROW']:
            raise ValidationError(f"Sheet '{sheet_name}' must have at least {config.EXCEL_CONFIG['DATA_START_ROW']} rows")
        
        # Validate metadata section
        validate_metadata_section(df, sheet_name)
        
        # Validate data section
        validate_data_section(df, sheet_name)
        
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(f"Error validating sheet '{sheet_name}': {str(e)}")

def validate_metadata_section(df: pd.DataFrame, sheet_name: str) -> None:
    """
    Validate metadata section (first 5 rows)
    
    Args:
        df: DataFrame to validate
        sheet_name: Name of the sheet for error messages
        
    Raises:
        ValidationError: If metadata is invalid
    """
    meta_rows = config.EXCEL_CONFIG['META_ROWS']
    meta_col_name = config.EXCEL_CONFIG['META_COL_NAME']
    meta_col_value = config.EXCEL_CONFIG['META_COL_VALUE']
    
    # Extract metadata
    meta_dict = {}
    for i in range(meta_rows):
        if i < len(df) and meta_col_name < len(df.columns) and meta_col_value < len(df.columns):
            field_name = str(df.iloc[i, meta_col_name]).strip()
            field_value = str(df.iloc[i, meta_col_value]).strip()
            
            if field_name in config.EXCEL_CONFIG['REQUIRED_META_FIELDS']:
                meta_dict[field_name] = field_value
    
    # Check required fields
    missing_fields = config.EXCEL_CONFIG['REQUIRED_META_FIELDS'] - set(meta_dict.keys())
    if missing_fields:
        raise ValidationError(f"Sheet '{sheet_name}' missing required metadata fields: {missing_fields}")
    
    # Validate lineName field
    if 'lineName' in meta_dict and not meta_dict['lineName']:
        raise ValidationError(f"Sheet '{sheet_name}' has empty lineName field")

def validate_data_section(df: pd.DataFrame, sheet_name: str) -> None:
    """
    Validate data section (rows 8+)
    
    Args:
        df: DataFrame to validate
        sheet_name: Name of the sheet for error messages
        
    Raises:
        ValidationError: If data section is invalid
    """
    header_row = config.EXCEL_CONFIG['HEADER_ROW']
    data_start_row = config.EXCEL_CONFIG['DATA_START_ROW']
    
    # Check if header row exists
    if header_row >= len(df):
        raise ValidationError(f"Sheet '{sheet_name}' missing header row")
    
    # Extract headers
    headers = df.iloc[header_row, 1:].astype(str).str.strip().tolist()
    
    # Check required columns
    required_columns = ['Station', 'Step', 'Title', 'Parts', 'Qty', 'Scan', 'Trace']
    missing_columns = [col for col in required_columns if col not in headers]
    if missing_columns:
        raise ValidationError(f"Sheet '{sheet_name}' missing required columns: {missing_columns}")
    
    # Check if there's any data
    if data_start_row >= len(df):
        raise ValidationError(f"Sheet '{sheet_name}' has no data rows")

def validate_json_data(data: Dict[str, Any]) -> None:
    """
    Validate JSON data structure before processing
    
    Args:
        data: JSON data to validate
        
    Raises:
        ValidationError: If JSON data is invalid
    """
    required_fields = ["scopeMaterialNumber", "operationsDefinitions"]
    
    for field in required_fields:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    
    # Validate operationsDefinitions
    if not isinstance(data.get("operationsDefinitions"), list):
        raise ValidationError("operationsDefinitions must be a list")
    
    # Validate each operation
    for i, operation in enumerate(data["operationsDefinitions"]):
        validate_operation(operation, i)

def validate_operation(operation: Dict[str, Any], index: int) -> None:
    """
    Validate individual operation structure
    
    Args:
        operation: Operation dictionary to validate
        index: Index of operation for error messages
        
    Raises:
        ValidationError: If operation is invalid
    """
    required_fields = ["operationTitle", "workstationName", "operationSegments"]
    
    for field in required_fields:
        if field not in operation:
            raise ValidationError(f"Operation {index} missing required field: {field}")
    
    # Validate operationSegments
    if not isinstance(operation.get("operationSegments"), list):
        raise ValidationError(f"Operation {index} operationSegments must be a list")
    
    # Validate each segment
    for j, segment in enumerate(operation["operationSegments"]):
        validate_segment(segment, index, j)

def validate_segment(segment: Dict[str, Any], operation_index: int, segment_index: int) -> None:
    """
    Validate individual segment structure
    
    Args:
        segment: Segment dictionary to validate
        operation_index: Index of operation for error messages
        segment_index: Index of segment for error messages
        
    Raises:
        ValidationError: If segment is invalid
    """
    required_fields = ["segmentTitle", "operationInputMaterials", "sampleDefinitions"]
    
    for field in required_fields:
        if field not in segment:
            raise ValidationError(f"Segment {operation_index}.{segment_index} missing required field: {field}")
    
    # Validate operationInputMaterials
    if not isinstance(segment.get("operationInputMaterials"), list):
        raise ValidationError(f"Segment {operation_index}.{segment_index} operationInputMaterials must be a list")
    
    # Validate sampleDefinitions
    if not isinstance(segment.get("sampleDefinitions"), list):
        raise ValidationError(f"Segment {operation_index}.{segment_index} sampleDefinitions must be a list")

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    from werkzeug.utils import secure_filename
    return secure_filename(filename)

def validate_line_names(line_names: List[str]) -> None:
    """
    Validate line names format
    
    Args:
        line_names: List of line names to validate
        
    Raises:
        ValidationError: If line names are invalid
    """
    if not line_names:
        raise ValidationError("At least one line name is required")
    
    for line_name in line_names:
        if not line_name.strip():
            raise ValidationError("Line names cannot be empty")
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in line_name:
                raise ValidationError(f"Line name '{line_name}' contains invalid character: {char}") 