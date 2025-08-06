import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    
    # API Configuration
    MES_API_URL = "https://mes.dev.figure.ai:60088/system/webdev/BotQ-MES/Operations/OperationsRouteManual"
    MES_USERNAME = os.getenv('MES_USERNAME', 'figure')
    MES_PASSWORD = os.getenv('MES_PASSWORD', 'figure')
    TIMEOUT_SECONDS = 600  # 10 minutes per file - increased from 500s to handle larger process plans
    
    # Excel Processing Configuration
    EXCEL_CONFIG = {
        'META_ROWS': 5,
        'HEADER_ROW': 7,
        'DATA_START_ROW': 8,
        'META_COL_NAME': 3,
        'META_COL_VALUE': 4,
        'REQUIRED_META_FIELDS': {
            "scopeMaterialNumber", "scopeMaterialTitle", 
            "scopeMaterialPlmId", "areaName", "lineName"
        }
    }
    
    # Material List
    MATERIAL_LIST = [
        "JADE", "SAPPHIRE", "LAPIS", "PAPAYA", "CARROT", "CITRINE", "MRC", "TACTILE", "FINGER", "FINGERMOTOR",
        "THUMBSENSOR", "THUMBMOTOR", "THUMB", "HANDPALM", "HANDCAMERAGLUE", "HAND",
        "ARMRIGHT", "ARMLEFT", "LEGRIGHT", "LEGLEFT", "SHIN", "NECKWRIST", 
        "PELVIS", "COMPUTE", "TORSOASSEMBLY", "FINALASSEMBLY", "BRINGUP",
        "BMSTEST", "CELLTEST", "BATTERYMAIN", "CASEPREPSUB", "BUSBARCCASUB", "BMSBOTTOMCOVERSUB"
    ]
    
    # EOL Testing Configuration
    EOL_TEST_ATTRIBUTES = {
        "testUUID": {
            "DataType": "STRING",
            "Required": True,
            "Description": "Defined by Test SW",
            "Format": "",
            "Order": 1,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testType": {
            "DataType": "STRING",
            "Required": True,
            "Description": "Test type, e.g. battery-pre-potting",
            "Format": "",
            "Order": 2,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testStatus": {
            "DataType": "STRING",
            "Required": True,
            "Description": "Status of test: PASS, FAIL, or ERROR",
            "Format": "",
            "Order": 3,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testErrorCode": {
            "DataType": "INTEGER",
            "Required": True,
            "Description": "Classifies type of error encountered (e.g., 0 if none)",
            "Format": "",
            "Order": 4,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testErrors": {
            "DataType": "STRING",
            "Required": True,
            "Description": "List of errors separated by semicolon",
            "Format": "",
            "Order": 5,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "rejectCode": {
            "DataType": "INTEGER",
            "Required": True,
            "Description": "Reject code classifying error type",
            "Format": "",
            "Order": 6,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "rejectReason": {
            "DataType": "STRING",
            "Required": True,
            "Description": "List of failed test parameters separated by semicolon",
            "Format": "",
            "Order": 7,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testRevision": {
            "DataType": "STRING",
            "Required": True,
            "Description": "Revision code",
            "Format": "",
            "Order": 8,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testCount": {
            "DataType": "INTEGER",
            "Required": True,
            "Description": "Number of tests run since permission granted",
            "Format": "",
            "Order": 9,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testTimestamp": {
            "DataType": "STRING",
            "Required": True,
            "Description": "Timestamp in 'YYYY-MM-DD HH:MM:SS UTC' format",
            "Format": "YYYY-MM-DD HH:mm:ss UTC",
            "Order": 10,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testDuration": {
            "DataType": "STRING",
            "Required": True,
            "Description": "Duration of test in 'HH:MM:SS' format",
            "Format": "HH:MM:SS",
            "Order": 11,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "urlString": {
            "DataType": "STRING",
            "Required": True,
            "Description": "URL to detailed test report",
            "Format": "URL",
            "Order": 12,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "operatorUserName": {
            "DataType": "STRING",
            "Required": True,
            "Description": "User name of operator starting tests",
            "Format": "",
            "Order": 13,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "operatorLevel": {
            "DataType": "STRING",
            "Required": True,
            "Description": "Operator level, e.g., OPERATOR or ADMIN",
            "Format": "",
            "Order": 14,
            "MinimumValue": "",
            "MaximumValue": ""
        },
        "testMetadata": {
            "DataType": "STRING",
            "Required": True,
            "Description": "Catch-all JSON string with additional test info",
            "Format": "JSON string",
            "Order": 15,
            "MinimumValue": "",
            "MaximumValue": ""
        }
    }

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

# Default configuration
config = DevelopmentConfig if os.getenv('FLASK_ENV') == 'development' else ProductionConfig 