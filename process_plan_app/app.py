from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_bcrypt import Bcrypt
import pandas as pd
import json
from flask_cors import CORS
import os
import tempfile
import zipfile
from PyPDF2 import PdfReader, PdfWriter
from werkzeug.utils import secure_filename
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import io
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from flask import flash, redirect, url_for
import logging
from config import config
from validators import ValidationError, validate_excel_file, validate_json_data, sanitize_filename, validate_line_names

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === App Setup ===
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Apply configuration
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['DEBUG'] = config.DEBUG

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.unauthorized_handler
def handle_unauthorized():
    return redirect(url_for('login'))

MATERIAL_LIST = [
    "JADE", "SAPPHIRE", "LAPIS", "PAPAYA", "CARROT", "CITRINE", "MRC", "TACTILE", "FINGER", "FINGERMOTOR",
    "THUMBSENSOR", "THUMBMOTOR", "THUMB", "HANDPALM", "HANDCAMERAGLUE", "HAND",
    "ARMRIGHT", "ARMLEFT", "LEGRIGHT", "LEGLEFT", "SHIN", "NECKWRIST", 
    "PELVIS", "COMPUTE", "TORSOASSEMBLY", "FINALASSEMBLY", "BRINGUP",
    "BMSTEST", "CELLTEST", "BATTERYMAIN", "CASEPREPSUB", "BUSBARCCASUB", "BMSBOTTOMCOVERSUB"
]


@app.template_filter('localtime')
def localtime_filter(utc_dt):
    if not utc_dt:
        return ""
    local_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/Los_Angeles"))  # or your local TZ
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')

# === User Model ===
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text, nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    role = db.Column(db.String(10), default='pending')  # 'admin', 'user', 'pending'
    is_approved = db.Column(db.Boolean, default=False)

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# === Utility Functions ===
def convert_bools(obj):
    if isinstance(obj, dict):
        return {k: convert_bools(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bools(i) for i in obj]
    elif isinstance(obj, bool):
        return "True" if obj else "False"
    return obj

def create_predefined_segment(line_name: str, station_str: str) -> dict:
    """Create predefined EOL testing segment with proper attributes"""
    return {
        "segmentTitle": "EOL Testing",
        "segmentName": "",
        "segmentPlmId": "",
        "segmentSequence": 0,
        "operationInputMaterials": [],
        "sampleDefinitions": [                
            {
                "instructions": "Place the part on the tester device",
                "sampleDefinitionName": line_name + "_" + station_str + "_Test",
                "plmId": "PLM_ID",
                "sampleClass": "EOL_Tester",
                "toolResourceInstance": "EOL_Tester_1",
                "sampleQty": 1,
                "settings": {"Configuration N/L/R": "N"},
                "attributes": config.EOL_TEST_ATTRIBUTES
            }
        ],
        "workInstruction": {
            "plmId": "PLM_ID",
            "pdfLink": ""
        }
    }

# === Registration ===
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']
            first_name = request.form['first_name']
            last_name = request.form['last_name']

            if User.query.filter_by(email=email).first():
                return "Email already exists.", 400

            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

            new_user = User(
                email=email,
                password_hash=hashed_pw,
                first_name=first_name,
                last_name=last_name,
                role='pending',
                is_approved=False
            )

            db.session.add(new_user)
            db.session.commit()
            
            logger.info(f"New user registered: {email}")
            return "Account request submitted. Await admin approval."
            
        except Exception as e:
            logger.error(f"Error during registration: {e}")
            return "Registration failed. Please try again.", 500

    return render_template('register.html')

# === Login ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                if not user.is_approved:
                    flash("Account is pending admin approval.", "error")
                    return redirect(url_for('login'))
                login_user(user)
                logger.info(f"User logged in: {email}")
                return redirect(url_for('index'))
            else:
                flash("Invalid email or password.", "error")
                return redirect(url_for('login'))
                
        except Exception as e:
            logger.error(f"Error during login: {e}")
            flash("Login failed. Please try again.", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

# === Logout ===
@app.route('/logout')
@login_required
def logout():
    logger.info(f"User logged out: {current_user.email}")
    logout_user()
    return redirect(url_for('login'))

# === Admin Approve ===
@app.route('/admin/approve', methods=['GET', 'POST'])
@login_required
def admin_approve():
    if current_user.role != 'admin':
        return "Access denied.", 403

    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id')
            action = request.form.get('action')
            
            user = User.query.get(user_id)
            if not user:
                return "User not found.", 404

            if action == 'approve':
                user.is_approved = True
                user.role = 'user'
                logger.info(f"User approved: {user.email}")
            elif action == 'reject':
                db.session.delete(user)
                logger.info(f"User rejected: {user.email}")

            db.session.commit()
            return redirect(url_for('admin_approve'))
            
        except Exception as e:
            logger.error(f"Error during admin approval: {e}")
            return "Approval failed. Please try again.", 500

    pending_users = User.query.filter_by(is_approved=False).all()
    return render_template('approve_users.html', users=pending_users)

# === Home / Index ===
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'json':
            try:
                file = request.files.get('file')
                material = request.form.get('material')

                if not file or not file.filename.endswith('.xlsx'):
                    return "Please upload a valid .xlsx file.", 400

                # Validate material selection
                if material not in config.MATERIAL_LIST:
                    return "Invalid material selection.", 400

                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_input:
                    file.save(temp_input.name)
                    with tempfile.TemporaryDirectory() as temp_output_dir:
                        json_files = process_excel_sheets_to_jsons(temp_input.name, temp_output_dir)
                        if not json_files:
                            return "No valid sheets found in the Excel file.", 400

                        zip_path = os.path.join(temp_output_dir, f"{material}_jsons.zip")
                        with zipfile.ZipFile(zip_path, 'w') as zipf:
                            for jf in json_files:
                                zipf.write(jf, os.path.basename(jf))
                        return send_file(zip_path, as_attachment=True, download_name=f"{material}_jsons.zip")
                        
            except ValidationError as e:
                logger.warning(f"Validation error in JSON generation: {e}")
                return str(e), 400
            except Exception as e:
                logger.error(f"Error in JSON generation: {e}")
                return "Error processing Excel file. Please check the file format.", 500

        elif form_type == 'pdf':
            try:
                uploaded_files = request.files.getlist('pdf_files')
                with tempfile.TemporaryDirectory() as temp_output_dir:
                    for file in uploaded_files:
                        if file and file.filename.lower().endswith(".pdf"):
                            filename = sanitize_filename(file.filename)
                            base_name = os.path.splitext(filename)[0]
                            pdf_path = os.path.join(temp_output_dir, filename)
                            file.save(pdf_path)

                            subfolder = os.path.join(temp_output_dir, base_name)
                            os.makedirs(subfolder, exist_ok=True)

                            reader = PdfReader(pdf_path)
                            for i in range(1, len(reader.pages)):
                                writer = PdfWriter()
                                writer.add_page(reader.pages[i])
                                output_name = f"{base_name}-{(i)*10:03}.pdf"
                                output_path = os.path.join(subfolder, output_name)
                                with open(output_path, "wb") as f_out:
                                    writer.write(f_out)

                    zip_path = os.path.join(temp_output_dir, "split_pdfs.zip")
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for root, _, files in os.walk(temp_output_dir):
                            for file in files:
                                full_path = os.path.join(root, file)
                                if full_path != zip_path:
                                    arcname = os.path.relpath(full_path, temp_output_dir)
                                    zipf.write(full_path, arcname)

                    return send_file(zip_path, as_attachment=True, download_name="split_pdfs.zip")
                    
            except Exception as e:
                logger.error(f"Error in PDF processing: {e}")
                return "Error processing PDF files.", 500

    # Pass current_user into the template to show admin options if needed
    return render_template("index.html", materials=config.MATERIAL_LIST, current_user=current_user)


# === JSON Import Route ===
@app.route('/import', methods=['POST'])
@login_required
def import_single_json():
    """Legacy single file import - kept for backward compatibility"""
    return import_multiple_jsons()

@app.route('/import-multiple', methods=['POST'])
@login_required
def import_multiple_jsons():
    """
    Import multiple JSON files sequentially.
    Continues on success (200), stops on first error.
    Each file gets its own history entry.
    """
    try:
        files = request.files.getlist('json_files')
        revision_note = request.form.get('revision_note', '').strip()
        
        if not files:
            logger.warning("No files uploaded")
            return jsonify({"error": "No files uploaded."}), 400

        # Validate that all files are JSON
        for file in files:
            if not file or not file.filename.endswith('.json'):
                logger.warning(f"Invalid file type: {file.filename if file else 'None'}")
                return jsonify({"error": f"Invalid file type: {file.filename}. Only .json files are allowed."}), 400

        results = []
        processed_count = 0
        total_files = len(files)
        
        logger.info(f"Starting batch import of {total_files} files")
        
        for i, file in enumerate(files):
            try:
                # Validate and sanitize filename
                filename = sanitize_filename(file.filename)
                
                logger.info(f"Processing file {i+1}/{total_files}: {filename}")
                
                # Read and validate JSON data
                raw_data = file.read()
                data = json.loads(raw_data.decode('utf-8'))
                validate_json_data(data)
                
                # Post to MES
                logger.info(f"Posting to MES with payload from {filename}")
                logger.debug(f"Payload preview: {json.dumps(data, indent=2)[:1000]}")

                response = requests.post(
                    config.MES_API_URL,
                    json=data,
                    auth=HTTPBasicAuth(config.MES_USERNAME, config.MES_PASSWORD),
                    headers={"Content-Type": "application/json"},
                    timeout=config.TIMEOUT_SECONDS
                )

                logger.info(f"MES Response for {filename}: {response.status_code}")
                logger.debug(f"Response preview: {response.text[:1000]}")

                # Save to DB regardless of status code
                history = ProcessPlanHistory(
                    user_email=current_user.email,
                    uploaded_filename=filename,
                    revision_note=revision_note,
                    status_code=str(response.status_code),
                    response_summary=response.text[:1000],
                    json_blob=raw_data
                )
                db.session.add(history)
                db.session.commit()
                
                # Check if successful
                if response.status_code == 200:
                    processed_count += 1
                    results.append({
                        "filename": filename,
                        "status_code": response.status_code,
                        "response": response.text[:1000],
                        "success": True
                    })
                    logger.info(f"Successfully imported JSON: {filename}")
                else:
                    # Non-200 status code - stop processing
                    error_msg = f"Import failed for {filename}. Status code: {response.status_code}"
                    logger.error(error_msg)
                    
                    results.append({
                        "filename": filename,
                        "status_code": response.status_code,
                        "response": response.text[:1000],
                        "success": False,
                        "error": error_msg
                    })
                    
                    # Return error with results so far
                    return jsonify({
                        "error": f"Import failed at file {i+1}/{total_files}: {filename}",
                        "processed_count": processed_count,
                        "total_files": total_files,
                        "results": results,
                        "failed_at": filename
                    }), 400
                    
            except ValidationError as e:
                logger.warning(f"Validation error for {filename}: {e}")
                # Save failed attempt to DB
                history = ProcessPlanHistory(
                    user_email=current_user.email,
                    uploaded_filename=filename,
                    revision_note=revision_note,
                    status_code="Validation Error",
                    response_summary=str(e),
                    json_blob=raw_data if 'raw_data' in locals() else b''
                )
                db.session.add(history)
                db.session.commit()
                
                results.append({
                    "filename": filename,
                    "status_code": "Validation Error",
                    "response": str(e),
                    "success": False,
                    "error": f"Validation error: {str(e)}"
                })
                
                return jsonify({
                    "error": f"Validation error at file {i+1}/{total_files}: {filename}",
                    "processed_count": processed_count,
                    "total_files": total_files,
                    "results": results,
                    "failed_at": filename
                }), 400
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON format for {filename}: {e}")
                # Save failed attempt to DB
                history = ProcessPlanHistory(
                    user_email=current_user.email,
                    uploaded_filename=filename,
                    revision_note=revision_note,
                    status_code="JSON Error",
                    response_summary=f"Invalid JSON format: {str(e)}",
                    json_blob=raw_data if 'raw_data' in locals() else b''
                )
                db.session.add(history)
                db.session.commit()
                
                results.append({
                    "filename": filename,
                    "status_code": "JSON Error",
                    "response": f"Invalid JSON format: {str(e)}",
                    "success": False,
                    "error": f"Invalid JSON format: {str(e)}"
                })
                
                return jsonify({
                    "error": f"Invalid JSON format at file {i+1}/{total_files}: {filename}",
                    "processed_count": processed_count,
                    "total_files": total_files,
                    "results": results,
                    "failed_at": filename
                }), 400
                
            except requests.exceptions.Timeout:
                logger.error(f"MES API request timed out for {filename}")
                # Save failed attempt to DB
                history = ProcessPlanHistory(
                    user_email=current_user.email,
                    uploaded_filename=filename,
                    revision_note=revision_note,
                    status_code="Timeout Error",
                    response_summary="Request timed out",
                    json_blob=raw_data if 'raw_data' in locals() else b''
                )
                db.session.add(history)
                db.session.commit()
                
                results.append({
                    "filename": filename,
                    "status_code": "Timeout Error",
                    "response": "Request timed out",
                    "success": False,
                    "error": "Request timed out"
                })
                
                return jsonify({
                    "error": f"Request timed out at file {i+1}/{total_files}: {filename}",
                    "processed_count": processed_count,
                    "total_files": total_files,
                    "results": results,
                    "failed_at": filename
                }), 408
                
            except requests.exceptions.RequestException as e:
                logger.error(f"MES API request failed for {filename}: {e}")
                # Save failed attempt to DB
                history = ProcessPlanHistory(
                    user_email=current_user.email,
                    uploaded_filename=filename,
                    revision_note=revision_note,
                    status_code="Request Error",
                    response_summary=f"Failed to connect to MES API: {str(e)}",
                    json_blob=raw_data if 'raw_data' in locals() else b''
                )
                db.session.add(history)
                db.session.commit()
                
                results.append({
                    "filename": filename,
                    "status_code": "Request Error",
                    "response": f"Failed to connect to MES API: {str(e)}",
                    "success": False,
                    "error": f"Failed to connect to MES API: {str(e)}"
                })
                
                return jsonify({
                    "error": f"Connection failed at file {i+1}/{total_files}: {filename}",
                    "processed_count": processed_count,
                    "total_files": total_files,
                    "results": results,
                    "failed_at": filename
                }), 503
                
            except Exception as e:
                logger.error(f"Unexpected error for {filename}: {e}")
                import traceback
                traceback.print_exc()
                
                # Save failed attempt to DB
                history = ProcessPlanHistory(
                    user_email=current_user.email,
                    uploaded_filename=filename,
                    revision_note=revision_note,
                    status_code="Unexpected Error",
                    response_summary=str(e),
                    json_blob=raw_data if 'raw_data' in locals() else b''
                )
                db.session.add(history)
                db.session.commit()
                
                results.append({
                    "filename": filename,
                    "status_code": "Unexpected Error",
                    "response": str(e),
                    "success": False,
                    "error": str(e)
                })
                
                return jsonify({
                    "error": f"Unexpected error at file {i+1}/{total_files}: {filename}",
                    "processed_count": processed_count,
                    "total_files": total_files,
                    "results": results,
                    "failed_at": filename
                }), 500

        # All files processed successfully
        logger.info(f"Successfully completed batch import: {processed_count}/{total_files} files")
        
        return jsonify({
            "success": True,
            "message": f"Successfully imported {processed_count}/{total_files} files",
            "processed_count": processed_count,
            "total_files": total_files,
            "results": results
        })

    except Exception as e:
        logger.error(f"Exception occurred during batch import: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"Batch import failed: {str(e)}",
            "processed_count": 0,
            "total_files": 0,
            "results": []
        }), 500

def process_excel_sheets_to_jsons(excel_file_path, output_dir):
    """
    Process Excel file and generate JSON files for each sheet and line name
    
    Args:
        excel_file_path: Path to the Excel file
        output_dir: Directory to save generated JSON files
        
    Returns:
        List of generated JSON file paths
        
    Raises:
        ValidationError: If Excel file is invalid
        RuntimeError: If processing fails
    """
    logger.info(f"Processing Excel file: {excel_file_path}")
    
    try:
        # Validate Excel file
        validate_excel_file(excel_file_path)
        
        xl = pd.ExcelFile(excel_file_path)
        generated_files = []

        for sheet_name in xl.sheet_names:
            try:
                logger.info(f"Processing sheet: {sheet_name}")
                
                df = xl.parse(sheet_name, header=None)
                if df.empty:
                    logger.warning(f"Sheet '{sheet_name}' is empty, skipping")
                    continue

                # Extract metadata using configuration
                meta_dict = {
                    str(df.iloc[i, config.EXCEL_CONFIG['META_COL_NAME']]).strip(): 
                    str(df.iloc[i, config.EXCEL_CONFIG['META_COL_VALUE']]).strip()
                    for i in range(config.EXCEL_CONFIG['META_ROWS'])
                    if pd.notna(df.iloc[i, config.EXCEL_CONFIG['META_COL_NAME']]) and 
                    str(df.iloc[i, config.EXCEL_CONFIG['META_COL_NAME']]).strip() in config.EXCEL_CONFIG['REQUIRED_META_FIELDS']
                }

                # Get line names and split by semicolon
                line_names_raw = meta_dict.get("lineName", "")
                line_names = [name.strip() for name in line_names_raw.split(';') if name.strip()]

                # Validate line names
                if line_names:
                    validate_line_names(line_names)
                else:
                    line_names = [""]

                # Create a JSON file for each line name
                for line_name in line_names:
                    try:
                        metadata = {
                            "scopeMaterialNumber": meta_dict.get("scopeMaterialNumber", ""),
                            "scopeMaterialTitle": meta_dict.get("scopeMaterialTitle", ""),
                            "scopeMaterialPlmId": meta_dict.get("scopeMaterialPlmId", "00000010"),
                            "areaName": meta_dict.get("areaName", ""),
                            "lineName": line_name,
                            "operationsDefinitions": []
                        }

                        # Extract headers and data using configuration
                        headers = df.iloc[config.EXCEL_CONFIG['HEADER_ROW'], 1:].astype(str).str.strip().tolist()
                        data_df = df.iloc[config.EXCEL_CONFIG['DATA_START_ROW']:, 1:1+len(headers)]
                        data_df.columns = headers

                        # Clean data
                        data_df["Station"] = data_df["Station"].ffill().infer_objects(copy=False)
                        data_df["Step"] = data_df["Step"].fillna("").astype(str).str.zfill(3)
                        data_df["Scan"] = data_df["Scan"].astype(str).str.lower().eq("true")
                        data_df["Trace"] = data_df["Trace"].astype(str).str.lower().eq("true")

                        for station, group in data_df.groupby("Station"):
                            station_int = int(station)
                            station_str = f"{station_int:03}"

                            predefined_segment = create_predefined_segment(line_name, station_str)

                            op_row = group[group["Step"] == "000"]
                            operation_title = op_row["Title"].values[0] if not op_row.empty else f"Station {station_str}"

                            operation = {
                                "operationTitle": operation_title,
                                "operationName": "",
                                "operationPlmId": "",
                                "workstationName": f"S{station_str}",
                                "operationSegments": []
                            }

                            if not op_row.empty and "cure buffer" in operation_title.lower():
                                # Create dynamic sample class from the Excel title
                                # Remove common words and clean up the title for use as sample class
                                sample_class_value = operation_title.strip()
                                # Remove "Buffer" and "buffer" variations
                                sample_class_value = sample_class_value.replace("Buffer", "").replace("buffer", "")
                                # Remove extra spaces and clean up
                                sample_class_value = " ".join(sample_class_value.split())
                                # Remove spaces for final sample class name
                                sample_class_value = sample_class_value.replace(" ", "")
                                
                                # If the result is empty or too short, use a default
                                if not sample_class_value or len(sample_class_value) < 2:
                                    sample_class_value = "CureBuffer"
                                
                                cure_buffer_segment = {
                                    "segmentTitle": operation_title,
                                    "segmentName": "",
                                    "segmentPlmId": "",
                                    "segmentSequence": 0,
                                    "operationInputMaterials": [],
                                    "sampleDefinitions": [
                                        {
                                            "instructions": "StartTimestamp",
                                            "sampleDefinitionName": "StartTimestamp",
                                            "plmId": "PLM_ID",
                                            "sampleClass": sample_class_value,
                                            "sampleQty": 1,
                                            "attributes": {
                                                "PassFail": {
                                                    "DataType": "BOOLEAN",
                                                    "Required": True,
                                                    "Description": "STRING",
                                                    "Format": "#0.00",
                                                    "Order": "1",
                                                    "MinimumValue": "",
                                                    "MaximumValue": ""
                                                }
                                            }
                                        },
                                        {
                                            "instructions": "EndTimestamp",
                                            "sampleDefinitionName": "EndTimestamp",
                                            "plmId": "PLM_ID",
                                            "sampleClass": sample_class_value,
                                            "sampleQty": 1,
                                            "attributes": {
                                                "PassFail": {
                                                    "DataType": "BOOLEAN",
                                                    "Required": True,
                                                    "Description": "STRING",
                                                    "Format": "#0.00",
                                                    "Order": "1",
                                                    "MinimumValue": "",
                                                    "MaximumValue": ""
                                                }
                                            }
                                        }
                                    ],
                                    "workInstruction": {
                                        "pdfLink": "",
                                        "plmId": "PLM_ID"
                                    }
                                }
                                operation["operationSegments"].append(cure_buffer_segment)

                            elif not op_row.empty and any(kw in operation_title.lower() for kw in ["test", "eol"]):
                                operation["operationSegments"].append(predefined_segment)
                            else:
                                step_groups = group[group["Step"] != "000"].groupby("Step")
                                
                                for step, step_rows in step_groups:
                                    materials = []
                                    
                                    # Process all rows for this step to collect materials (exclude Manual Entry)
                                    for _, row in step_rows.iterrows():
                                        if pd.notna(row.get("Parts")) and row.get("Tools") != "Manual Entry":
                                            # Determine units - use "Unit" column if available, otherwise default to "each"
                                            units_value = "each"  # default value
                                            if "Unit" in row.index and pd.notna(row.get("Unit")):
                                                units_value = str(row["Unit"]).strip()
                                            elif "unit" in row.index and pd.notna(row.get("unit")):
                                                units_value = str(row["unit"]).strip()
                                            
                                            materials.append({
                                                "inputMaterialPMlmId": "PLM_ID",
                                                "materialName": "",
                                                "quantity": int(row["Qty"]) if pd.notna(row["Qty"]) else 1,
                                                "materialNumber": str(row["Parts"]).strip(),
                                                "materialTitle": "",
                                                "units": units_value,
                                                "scan": "True" if row["Scan"] else "False",
                                                "parentIdentifier": "True" if row["Trace"] else "False"
                                            })

                                    # Use the first row for segment details
                                    first_row = step_rows.iloc[0]
                                    
                                    sample_definitions = []

                                    # Confirm sample
                                    confirm_sample = {
                                        "instructions": "Next?",
                                        "sampleDefinitionName": line_name + "Confirm" if line_name else "",
                                        "plmId": "PLM_ID",
                                        "sampleClass": "Confirm",
                                        "sampleQty": 1,
                                        "attributes": {
                                            "PassFail": {
                                                "DataType": "BOOLEAN",
                                                "Required": True,
                                                "Description": "STRING",
                                                "Format": "#0.00",
                                                "Order": "1",
                                                "MinimumValue": "",
                                                "MaximumValue": ""
                                            }
                                        }
                                                                        }
                                    sample_definitions.append(confirm_sample)

                                    # Handle different tool types
                                    if pd.notna(first_row.get("Tools")):
                                        if first_row["Tools"] == "Manual Entry":
                                            # Get the dynamic attribute name from Parts column
                                            parts_value = str(first_row["Parts"]).strip() if pd.notna(first_row.get("Parts")) else "ManualEntry"
                                            
                                            # Manual Entry sample with dynamic attribute from Parts column
                                            manual_entry_sample = {
                                                "instructions": first_row["Title"],
                                                "sampleDefinitionName": parts_value,
                                                "plmId": "PLM_ID",
                                                "sampleClass": "Manual Entry",
                                                "sampleQty": int(first_row["Qty"]) if pd.notna(first_row["Qty"]) else 1,
                                                "attributes": {
                                                    parts_value: {
                                                        "DataType": "REAL",
                                                        "Required": True,
                                                        "Description": parts_value,
                                                        "Format": "#0.00",
                                                        "Order": "1",
                                                        "MinimumValue": "",
                                                        "MaximumValue": ""
                                                    }
                                                }
                                            }
                                            sample_definitions.append(manual_entry_sample)
                                        elif first_row["Tools"] != "Manual Entry" and pd.notna(first_row.get("Pset Program Number")):
                                            # Torque sample
                                            torque_sample = {
                                                "instructions": first_row["Title"],
                                                "sampleDefinitionName": line_name + "Torque" if line_name else "",
                                                "plmId": "PLM_ID",
                                                "toolResourceInstance": first_row["Tools"],
                                                "sampleClass": "Torque",
                                                "sampleQty": int(first_row["Qty"]) if pd.notna(first_row["Qty"]) else 1,
                                                "settings": {
                                                    "pSet": str(first_row["Pset Program Number"])
                                                },
                                                "attributes": {
                                                    "PassFail": {
                                                        "DataType": "BOOLEAN",
                                                        "Required": True,
                                                        "Description": "STRING",
                                                        "Format": "#0.00",
                                                        "Order": 1,
                                                        "MinimumValue": "",
                                                        "MaximumValue": ""
                                                    },
                                                    "Torque": {
                                                        "DataType": "REAL",
                                                        "Required": True,
                                                        "Description": "STRING",
                                                        "Format": "#0.00",
                                                        "Order": 2,
                                                        "NominalValue": "1.5",
                                                        "MinimumValue": "1.3",
                                                        "MaximumValue": "1.7"
                                                    },
                                                    "Angle": {
                                                        "DataType": "REAL",
                                                        "Required": True,
                                                        "Description": "STRING",
                                                        "Format": "#0.00",
                                                        "Order": 3,
                                                        "MinimumValue": "",
                                                        "MaximumValue": "",
                                                        "NominalValue": ""
                                                    },
                                                    "PSet": {
                                                        "DataType": "INTEGER",
                                                        "Required": True,
                                                        "Description": "STRING",
                                                        "Format": "#0.00",
                                                        "Order": 4,
                                                        "MinimumValue": "",
                                                        "MaximumValue": ""
                                                    }
                                                }
                                            }
                                            sample_definitions.append(torque_sample)

                                    # Build segment
                                    segment = {
                                        "segmentTitle": first_row["Title"],
                                        "segmentName": "",
                                        "segmentPlmId": "",
                                        "segmentSequence": 0,
                                        "operationInputMaterials": materials,
                                        "sampleDefinitions": sample_definitions,
                                    }

                                    # Optional customActions if Fixture is provided
                                    custom_actions = []
                                    if pd.notna(first_row.get("Fixture")) and str(first_row["Fixture"]).strip():
                                        custom_actions.append({
                                            "actionType": "Scan Fixture",
                                            "actionTarget": str(first_row["Fixture"]).strip(),
                                            "actionSettings": {}
                                        })

                                    if custom_actions:
                                        segment["customActions"] = custom_actions

                                    # Work instruction block
                                    segment["workInstruction"] = {
                                        "pdfLink": first_row["Work Instruction"] if pd.notna(first_row["Work Instruction"]) else "",
                                        "plmId": "PLM_ID"
                                    }

                                    operation["operationSegments"].append(segment)

                            metadata["operationsDefinitions"].append(operation)

                        # Create filename with line name
                        if line_name:
                            filename = f"{sheet_name.strip()}_{line_name}.json"
                        else:
                            filename = f"{sheet_name.strip()}.json"
                        
                        output_path = os.path.join(output_dir, filename)
                        
                        # Validate JSON data before saving
                        validate_json_data(metadata)
                        
                        with open(output_path, "w", encoding="utf-8") as f:
                            json.dump(convert_bools(metadata), f, indent=2)
                        generated_files.append(output_path)
                        
                        logger.info(f"Generated JSON file: {output_path}")
                        
                    except Exception as e:
                        logger.error(f"Error processing line name '{line_name}' for sheet '{sheet_name}': {e}")
                        continue

            except Exception as e:
                logger.error(f"Error processing sheet '{sheet_name}': {e}")
                continue

        logger.info(f"Successfully generated {len(generated_files)} JSON files")
        return generated_files

    except Exception as e:
        logger.error(f"Error processing Excel file: {e}")
        raise RuntimeError(f"Error processing Excel file: {e}")


# === Added Route history === #
@app.route('/history')
@login_required
def process_history():
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)  # Default 50 entries per page
    search = request.args.get('search', '', type=str)
    
    # Build query with search filter
    query = ProcessPlanHistory.query
    
    if search:
        query = query.filter(
            db.or_(
                ProcessPlanHistory.user_email.ilike(f'%{search}%'),
                ProcessPlanHistory.uploaded_filename.ilike(f'%{search}%'),
                ProcessPlanHistory.revision_note.ilike(f'%{search}%')
            )
        )
    
    # Order by upload time (newest first) and paginate
    pagination = query.order_by(ProcessPlanHistory.upload_time.desc()).paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    history = pagination.items
    
    return render_template('process_history.html', 
                         history=history, 
                         pagination=pagination,
                         search=search,
                         per_page=per_page)

@app.route('/history/json')
@login_required
def process_history_json():
    """AJAX endpoint to get history data in JSON format for auto-refresh"""
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '', type=str)
    
    # Build query with search filter
    query = ProcessPlanHistory.query
    
    if search:
        query = query.filter(
            db.or_(
                ProcessPlanHistory.user_email.ilike(f'%{search}%'),
                ProcessPlanHistory.uploaded_filename.ilike(f'%{search}%'),
                ProcessPlanHistory.revision_note.ilike(f'%{search}%')
            )
        )
    
    # Order by upload time (newest first) and paginate
    pagination = query.order_by(ProcessPlanHistory.upload_time.desc()).paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    # Convert history items to JSON-serializable format
    history_data = []
    for item in pagination.items:
        history_data.append({
            'id': item.id,
            'user_email': item.user_email,
            'uploaded_filename': item.uploaded_filename,
            'upload_time': item.upload_time.isoformat() if item.upload_time else None,
            'status_code': item.status_code,
            'revision_note': item.revision_note
        })
    
    return jsonify({
        'history': history_data,
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_num': pagination.prev_num,
            'next_num': pagination.next_num
        },
        'search': search
    })


# ===  Create a route to download JSON from DB as a file === #
@app.route('/download_json/<int:history_id>')
@login_required
def download_json_blob(history_id):  # ✅ name changed
    record = ProcessPlanHistory.query.get_or_404(history_id)

    if not record.json_blob:
        return "No JSON blob stored for this record.", 404

    return send_file(
        io.BytesIO(record.json_blob),
        mimetype='application/json',
        as_attachment=True,
        download_name=record.uploaded_filename
    )



# === Create New Model for History Logs === #

class ProcessPlanHistory(db.Model):
    __tablename__ = 'process_plan_history'

    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=False)
    uploaded_filename = db.Column(db.String(255), nullable=False)
    revision_note = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=db.func.now())
    status_code = db.Column(db.String(20))
    response_summary = db.Column(db.Text)
    json_blob = db.Column(db.LargeBinary)  # <-- added


    
# === Run the App ===
if __name__ == '__main__':
    app.run(debug=True)
