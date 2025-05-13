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
load_dotenv()
# === App Setup ===
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
app.config['SECRET_KEY'] = 'supersecretkey'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

MATERIAL_LIST = [
    "SAPPHIRE", "LAPIS", "JADE", "CARROT",
    "CITRINE", "PAPAYA", "FINGER"
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
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.check_password(request.form['password']):
            if not user.is_approved:
                return "Account pending approval.", 403
            login_user(user)
            return redirect('/')
        return "Invalid credentials.", 403
    return render_template('login.html')

# === Logout ===
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# === Admin: Approve Users ===
@app.route('/admin/approve', methods=['GET', 'POST'])
@login_required
def admin_approve():
    if current_user.role != 'admin':
        return "Unauthorized", 403
    if request.method == 'POST':
        user_id = request.form['user_id']
        user = User.query.get(user_id)
        if user:
            user.is_approved = True
            user.role = 'user'
            db.session.commit()
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
            timeout=120
        )

        print(f"✅ MES Response: {response.status_code}")
        print(response.text[:1000])  # Only first 1000 chars

        # Save to DB
        history = ProcessPlanHistory(
            user_email=current_user.email,
            uploaded_filename=file.filename,
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

            metadata = {
                "scopeMaterialNumber": meta_dict.get("scopeMaterialNumber", ""),
                "scopeMaterialTitle": meta_dict.get("scopeMaterialTitle", ""),
                "scopeMaterialPlmId": meta_dict.get("scopeMaterialPlmId", "00000010"),
                "areaName": meta_dict.get("areaName", ""),
                "lineName": meta_dict.get("lineName", ""),
                "operationsDefinitions": []
            }

            headers = df.iloc[7, 1:].astype(str).str.strip().tolist()
            data_df = df.iloc[8:, 1:1+len(headers)]
            data_df.columns = headers

            data_df["Station"] = data_df["Station"].ffill().infer_objects(copy=False)
            data_df["Step"] = data_df["Step"].fillna("").astype(str).str.zfill(3)
            data_df["Scan"] = data_df["Scan"].astype(str).str.lower().eq("true")
            data_df["Trace"] = data_df["Trace"].astype(str).str.lower().eq("true")

            predefined_segment = {
                "segmentTitle": "EOL Testing",
                "segmentName": "",
                "segmentPlmId": "",
                "segmentSequence": 0,
                "operationInputMaterials": [],
                "sampleDefinitions": [                
                    {
                        "instructions": "Place the part on the tester device",
                        "sampleDefinitionName": "",
                        "plmId": "PLM_ID",
                        "sampleClass": "Actuator EOL Tester",
                        "toolResourceInstance": "Actuator_Tester_1",
                        "sampleQty": 3,
                        "settings": {"Configuration N/L/R": "N"},
                        "attributes": {
                            "PassFail": {
                                "DataType": "BOOLEAN", "Required": True, "Description": "Pass or fail result", "Format": "", "Order": 1,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "TestRevision": {
                                "DataType": "STRING", "Required": True, "Description": "Revision code", "Format": "DW", "Order": 2,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "TestCount": {
                                "DataType": "INTEGER", "Required": True, "Description": "Number of test repetitions", "Format": "", "Order": 3,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "TestTimestamp": {
                                "DataType": "STRING", "Required": True, "Description": "Time of test", "Format": "", "Order": 4,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "TestDuration": {
                                "DataType": "INTEGER", "Required": True, "Description": "Duration of test (in s)", "Format": "", "Order": 5,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "RejectCode": {
                                "DataType": "STRING", "Required": True, "Description": "Code for rejection reason", "Format": "", "Order": 6,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "RejectReason": {
                                "DataType": "STRING", "Required": True, "Description": "Description of rejection reason", "Format": "DW", "Order": 7,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "URLString": {
                                "DataType": "STRING", "Required": True, "Description": "Link to related documentation", "Format": "DW", "Order": 8,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "OperatorDetails": {
                                "DataType": "STRING", "Required": True, "Description": "Name or ID of operator", "Format": "DW", "Order": 9,
                                "MinimumValue": "", "MaximumValue": ""
                            },
                            "TestType": {
                                "DataType": "STRING", "Required": True, "Description": "Type of test performed", "Format": "DW", "Order": 10,
                                "MinimumValue": "", "MaximumValue": ""
                            }
                        }
                    }
                ],
                "workInstruction": {"plmId": "PLM_ID", "pdfLink": ""}
            }

            for station, group in data_df.groupby("Station"):
                station_int = int(station)
                station_str = f"{station_int:03}"

                op_row = group[group["Step"] == "000"]
                operation_title = op_row["Title"].values[0] if not op_row.empty else f"Station {station_str}"

                operation = {
                    "operationTitle": operation_title,
                    "operationName": "",
                    "operationPlmId": "",
                    "workstationName": f"S{station_str}",
                    "operationSegments": []
                }

                if not op_row.empty and any(kw in operation_title.lower() for kw in ["test", "eol"]):
                    operation["operationSegments"].append(predefined_segment)
                else:
                    step_groups = group[group["Step"] != "000"].groupby("Step")

                    for step, rows in step_groups:
                        row = rows.iloc[0]
                        materials = []

                        for _, r in rows.iterrows():
                            if pd.notna(r.get("Parts")):
                                materials.append({
                                    "inputMaterialPMlmId": "PLM_ID",
                                    "materialName": "",
                                    "quantity": int(r["Qty"]) if pd.notna(r["Qty"]) else 1,
                                    "materialNumber": str(r["Parts"]).strip(),
                                    "materialTitle": "",
                                    "units": "each",
                                    "scan": "True" if r["Scan"] else "False",
                                    "parentIdentifier": "True" if r["Trace"] else "False"
                                })

                        segment = {
                            "segmentTitle": row["Title"],
                            "segmentName": "",
                            "segmentPlmId": "",
                            "segmentSequence": 0,
                            "operationInputMaterials": materials,
                            "sampleDefinitions": [
                                {
                                    "instructions": "Next?",
                                    "sampleDefinitionName": "",
                                    "plmId": "PLM_ID",
                                    "sampleClass": "Confirm",
                                    "sampleQty": 1,
                                    "attributes": {
                                        "PassFail": {
                                            "DataType": "BOOLEAN", "Required": True, "Description": "STRING", "Format": "#0.00", "Order": "1",
                                            "MinimumValue": "", "MaximumValue": ""
                                        }
                                    }
                                }
                            ],
                            "workInstruction": {
                                "pdfLink": row["Work Instruction"] if pd.notna(row["Work Instruction"]) else "",
                                "plmId": "PLM_ID"
                            }
                        }

                        operation["operationSegments"].append(segment)

                metadata["operationsDefinitions"].append(operation)
                metadata["operationsDefinitions"].append(operation)
                output_path = os.path.join(output_dir, f"{sheet_name.strip()}.json")
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
    upload_time = db.Column(db.DateTime, default=db.func.now())
    status_code = db.Column(db.String(20))
    response_summary = db.Column(db.Text)
    json_blob = db.Column(db.LargeBinary)  # <-- added


    
# === Run the App ===
if __name__ == '__main__':
    app.run(debug=True)
