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
load_dotenv()
# === App Setup ===
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
app.config['SECRET_KEY'] = 'supersecretkey'
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
    email = db.Column(db.String(255), unique=True, nullable=False)
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

# === Registration ===
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
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

        return "Account request submitted. Await admin approval."

    return render_template('register.html')


# === Login ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_approved:
                flash("Account is pending admin approval.", "error")
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password.", "error")
            return redirect(url_for('login'))

    return render_template('login.html')


# === Logout ===
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# === Admin: Approve or Deny Users ===
@app.route('/admin/approve', methods=['GET', 'POST'])
@login_required
def admin_approve():
    if current_user.role != 'admin':
        flash("Access denied. Admins only.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        user = User.query.get(user_id)

        if not user:
            flash("User not found.", "error")
        elif action == 'approve':
            user.is_approved = True
            user.role = 'user'
            db.session.commit()
            flash(f"Approved {user.email}.", "success")
        elif action == 'deny':
            db.session.delete(user)
            db.session.commit()
            flash(f"Denied and removed {user.email}.", "warning")
        else:
            flash("Invalid action.", "error")

        return redirect(url_for('admin_approve'))

    pending_users = User.query.filter_by(is_approved=False).all()
    return render_template('approve_users.html', users=pending_users)


# === Home / Index ===
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'json':
            file = request.files.get('file')
            material = request.form.get('material')

            if not file or not file.filename.endswith('.xlsx'):
                return "Please upload a valid .xlsx file.", 400

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

        elif form_type == 'pdf':
            uploaded_files = request.files.getlist('pdf_files')
            with tempfile.TemporaryDirectory() as temp_output_dir:
                for file in uploaded_files:
                    if file and file.filename.lower().endswith(".pdf"):
                        filename = secure_filename(file.filename)
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

    # Pass current_user into the template to show admin options if needed
    return render_template("index.html", materials=MATERIAL_LIST, current_user=current_user)


# === JSON Import Route ===


@app.route('/import', methods=['POST'])
@login_required
def import_single_json():
    file = request.files.get('json_file')
    revision_note = request.form.get('revision_note', '').strip()
    if not file or not file.filename.endswith('.json'):
        print("❌ Invalid file uploaded or missing")
        return jsonify({"error": "Invalid file type."}), 400

    try:
        raw_data = file.read()
        data = json.loads(raw_data.decode('utf-8'))
        print("📤 Posting to MES with payload:")
        print(json.dumps(data, indent=2)[:1000])  # Log first 1000 chars for safety

        response = requests.post(
            "https://mes.dev.figure.ai:60088/system/webdev/BotQ-MES/Operations/OperationsRouteManual",
            json=data,
            auth=HTTPBasicAuth('figure', 'figure'),
            headers={"Content-Type": "application/json"},
            timeout=600
        )

        print(f"✅ MES Response: {response.status_code}")
        print(response.text[:1000])  # Only first 1000 chars

        # Save to DB
        history = ProcessPlanHistory(
            user_email=current_user.email,
            uploaded_filename=file.filename,
            revision_note=revision_note,
            status_code=str(response.status_code),
            response_summary=response.text[:1000],
            json_blob=raw_data
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({
            "filename": file.filename,
            "status_code": response.status_code,
            "response": response.text[:1000]
        })

    except Exception as e:
        print("❌ Exception occurred during /import:")
        import traceback
        traceback.print_exc()  # Logs full stack trace
        return jsonify({
            "filename": file.filename if file else "N/A",
            "status_code": "Error",
            "response": str(e)
        })

def convert_bools(obj):
    if isinstance(obj, dict):
        return {k: convert_bools(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bools(item) for item in obj]
    elif isinstance(obj, bool):
        return str(obj)
    return obj

def process_excel_sheets_to_jsons(excel_file_path, output_dir):
    xl = pd.ExcelFile(excel_file_path)
    generated_files = []

    for sheet_name in xl.sheet_names:
        try:
            df = xl.parse(sheet_name, header=None)
            if df.empty:
                continue

            meta_dict = {
                str(df.iloc[i, 3]).strip(): str(df.iloc[i, 4]).strip()
                for i in range(5)
                if pd.notna(df.iloc[i, 3]) and str(df.iloc[i, 3]).strip() in {
                    "scopeMaterialNumber", "scopeMaterialTitle", "scopeMaterialPlmId", "areaName", "lineName"
                }
            }

            # Get line names and split by semicolon
            line_names_raw = meta_dict.get("lineName", "")
            line_names = [name.strip() for name in line_names_raw.split(';') if name.strip()]

            # If no line names found, use a default
            if not line_names:
                line_names = [""]

            # Create a JSON file for each line name
            for line_name in line_names:
                metadata = {
                    "scopeMaterialNumber": meta_dict.get("scopeMaterialNumber", ""),
                    "scopeMaterialTitle": meta_dict.get("scopeMaterialTitle", ""),
                    "scopeMaterialPlmId": meta_dict.get("scopeMaterialPlmId", "00000010"),
                    "areaName": meta_dict.get("areaName", ""),
                    "lineName": line_name,
                    "operationsDefinitions": []
                }

                headers = df.iloc[7, 1:].astype(str).str.strip().tolist()
                data_df = df.iloc[8:, 1:1+len(headers)]
                data_df.columns = headers

                data_df["Station"] = data_df["Station"].ffill().infer_objects(copy=False)
                data_df["Step"] = data_df["Step"].fillna("").astype(str).str.zfill(3)
                data_df["Scan"] = data_df["Scan"].astype(str).str.lower().eq("true")
                data_df["Trace"] = data_df["Trace"].astype(str).str.lower().eq("true")

                for station, group in data_df.groupby("Station"):
                    station_int = int(station)
                    station_str = f"{station_int:03}"

                    predefined_segment = {
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
                                "attributes": {
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
                                    "testStartTime": {
                                        "DataType": "STRING",
                                        "Required": True,
                                        "Description": "ISO 8601 timestamp when test started",
                                        "Format": "",
                                        "Order": 6,
                                        "MinimumValue": "",
                                        "MaximumValue": ""
                                    },
                                    "testEndTime": {
                                        "DataType": "STRING",
                                        "Required": True,
                                        "Description": "ISO 8601 timestamp when test ended",
                                        "Format": "",
                                        "Order": 7,
                                        "MinimumValue": "",
                                        "MaximumValue": ""
                                    },
                                    "testDuration": {
                                        "DataType": "INTEGER",
                                        "Required": True,
                                        "Description": "Test duration in seconds",
                                        "Format": "",
                                        "Order": 8,
                                        "MinimumValue": "",
                                        "MaximumValue": ""
                                    },
                                    "testResults": {
                                        "DataType": "STRING",
                                        "Required": True,
                                        "Description": "JSON string containing test results",
                                        "Format": "",
                                        "Order": 9,
                                        "MinimumValue": "",
                                        "MaximumValue": ""
                                    }
                                }
                            }
                        ],
                        "workInstruction": {
                            "plmId": "PLM_ID",
                            "pdfLink": ""
                        }
                    }

                    op_row = group[group["Step"] == "000"]
                    operation_title = op_row["Title"].values[0] if not op_row.empty else f"Station {station_str}"

                    operation = {
                        "operationTitle": operation_title,
                        "operationName": "",
                        "operationPlmId": "",
                        "workstationName": f"S{station_str}",
                        "operationSegments": []
                    }

                    if not op_row.empty and any(keyword in str(operation_title) for keyword in ["EOL", "Test", "test"]):
                        operation["operationSegments"].append(predefined_segment)
                    else:
                        step_rows = group[group["Step"] != "000"]
                        for _, row in step_rows.iterrows():
                            materials = []
                            if pd.notna(row.get("Parts")):
                                materials.append({
                                    "inputMaterialPMlmId": "PLM_ID",
                                    "materialName": "",
                                    "quantity": int(row["Qty"]) if pd.notna(row["Qty"]) else 1,
                                    "materialNumber": str(row["Parts"]).strip(),
                                    "materialTitle": "",
                                    "units": "each",
                                    "scan": "True" if row["Scan"] else "False",
                                    "parentIdentifier": "True" if row["Trace"] else "False"
                                })

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

                            # Torque sample
                            if pd.notna(row.get("Tools")) and pd.notna(row.get("Pset Program Number")):
                                torque_sample = {
                                    "instructions": row["Title"],
                                    "sampleDefinitionName": line_name + "Torque" if line_name else "",
                                    "plmId": "PLM_ID",
                                    "toolResourceInstance": row["Tools"],
                                    "sampleClass": "Torque",
                                    "sampleQty": int(row["Qty"]) if pd.notna(row["Qty"]) else 1,
                                    "settings": {
                                        "pSet": str(row["Pset Program Number"])
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
                                "segmentTitle": row["Title"],
                                "segmentName": "",
                                "segmentPlmId": "",
                                "segmentSequence": 0,
                                "operationInputMaterials": materials,
                                "sampleDefinitions": sample_definitions,
                            }

                            # Optional customActions if Fixture is provided
                            custom_actions = []
                            if pd.notna(row.get("Fixture")) and str(row["Fixture"]).strip():
                                custom_actions.append({
                                    "actionType": "Scan Fixture",
                                    "actionTarget": str(row["Fixture"]).strip(),
                                    "actionSettings": {}
                                })

                            if custom_actions:
                                segment["customActions"] = custom_actions

                            # Work instruction block
                            segment["workInstruction"] = {
                                "pdfLink": row["Work Instruction"] if pd.notna(row["Work Instruction"]) else "",
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
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(convert_bools(metadata), f, indent=2)
                generated_files.append(output_path)

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Error processing sheet '{sheet_name}': {e}")

    return generated_files


# === Added Route history === #
@app.route('/history')
@login_required
def process_history():
    history = ProcessPlanHistory.query.order_by(ProcessPlanHistory.upload_time.desc()).all()
    return render_template('process_history.html', history=history)



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
