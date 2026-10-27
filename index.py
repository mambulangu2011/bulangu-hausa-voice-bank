import os, json, uuid, sqlite3, zipfile, io, csv
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, session, send_file, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'bulangu-v9.1-full-metadata-2026-GOOGLE-MOZILLA-OPENAI'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
DB_PATH = '/tmp/bulangu_v9_full.db'
UPLOAD_FOLDER = '/tmp/uploads_v9_full'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS voices (
        id TEXT PRIMARY KEY,
        speaker_id TEXT,
        speaker_name TEXT,
        age INTEGER,
        age_group TEXT,
        gender TEXT,
        dialect TEXT,
        birth_state TEXT,
        birth_lga TEXT,
        current_state TEXT,
        current_lga TEXT,
        ward TEXT,
        village TEXT,
        gps_lat TEXT,
        gps_long TEXT,
        education_level TEXT,
        occupation TEXT,
        languages_spoken TEXT,
        literacy_hausa TEXT,
        literacy_english TEXT,
        voice_type TEXT,
        prompt_id TEXT,
        prompt_text TEXT,
        transcription TEXT,
        audio_filename TEXT,
        duration REAL,
        sampling_rate TEXT,
        file_format TEXT,
        device_type TEXT,
        device_model TEXT,
        recording_env TEXT,
        noise_level TEXT,
        quality_score TEXT,
        consent INTEGER,
        consent_date TEXT,
        license TEXT,
        payment_type TEXT,
        payment_amount TEXT,
        collector_name TEXT,
        created_at TEXT
    )
    """)
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT)")
    c.execute("SELECT * FROM users WHERE username='Bulangu'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username,password) VALUES (?,?)", ('Bulangu', generate_password_hash('Bulangu123')))
    conn.commit(); conn.close()
init_db()

PROMPTS = {
 "conversational": ["Ina yaro yake? Yana kasuwa.","Yau kasuwa ta yi tsada sosai.","Gobe za mu je gona da safe.","Kin ci abinci? Na ci, na gode."],
 "reading": ["Hausa harshe ne mai matukar muhimmanci a Afirka ta Yamma.","Ilimi shi ne ginshikin cigaban kasa.","Ruwan sama ya sa albarka a gonakinmu a bana."],
 "code_switch": ["Ina zuwa market zan sayo rice da beans.","Please ka bani water, ina jin thirsty.","My phone ya bata, ina neman repairer."],
 "numbers_commands": ["Daya, Biyu, Uku, Hudu, Biyar","Bude kofa, rufe taga, kunna wuta","Lambar wayata sifili takwas daya"],
 "emotion": ["Yau ina farin ciki sosai! Na samu nasara!","Ina bakin ciki, abokina ya tafi.","Wannan abin ya bani mamaki matuka!"],
 "domain_health": ["Yaro na fama da zazzabi da tari tun jiya.","Wanke hannu na hana yaduwar cututtuka.","Mata masu juna biyu su je awon ciki."],
 "domain_agriculture": ["Noman shinkafa na bukatar ruwa mai yawa.","Takin zamani na kara yawan amfanin gona.","Farashin taki ya tashi a kasuwar Ringim."],
 "real_world_noisy": ["A kasuwa hayaniya ce!","A mota direba yana kara kida.","Yara suna kuka a gida."]
}
VOICE_LABELS = {"conversational":"1. Hira Conversational $50/h","reading":"2. Karatu TTS","code_switch":"3. Code-switch Hausa+Eng","numbers_commands":"4. Lamba & Umurni","emotion":"5. Emotion","domain_health":"6. Lafiya/Finance","domain_agriculture":"7. Noma","real_world_noisy":"8. Noisy Real World"}
DIALECTS = ["Sakkwatanci","Katsinanci","Kananci","Zazzagawa","Arewanci","Bulanguanci","Hadanci","Dauranci","Others"]
STATES = ["Jigawa","Kano","Katsina","Sokoto","Zamfara","Kaduna","Bauchi","Kebbi","Niger","Others"]

HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bulangu V9.1 Full Metadata</title><style>
*{box-sizing:border-box}body{font-family:system-ui;background:#f5f7fb;margin:0}
.header{background:linear-gradient(135deg,#0f172a,#1e40af);color:#fff;padding:16px;position:sticky;top:0}
.container{max-width:1200px;margin:auto;padding:14px}.card{background:#fff;border-radius:12px;padding:16px;margin-bottom:14px;box-shadow:0 2px 10px rgba(0,0,0,.06)}
label{font-size:11px;font-weight:700;color:#334155;display:block;margin:8px 0 3px}
input,select,textarea{width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.btn{padding:10px 14px;border:0;border-radius:8px;font-weight:800;cursor:pointer}
.btn-p{background:#2563eb;color:#fff}.btn-s{background:#059669;color:#fff}.btn-d{background:#0f172a;color:#fff}
.prompt-box{background:#f1f5f9;border:1px dashed #94a3b8;padding:8px;border-radius:8px;margin:4px 0;cursor:pointer;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:7px;border-bottom:1px solid #e2e8f0;text-align:left}
</style></head><body>
<div class="header"><h1 style="margin:0;font-size:18px">🎙️ BULANGU V9.1 - FULL METADATA FOR GOOGLE/MOZILLA/OPENAI</h1><p style="margin:4px 0 0;font-size:12px;opacity:.9">State, LGA, Ward, Birthplace, GPS, Dialect, Device, Consent, License - Komai da suke bukata</p></div>
<div class="container">
<div class="card"><b>Total: {{total}} | Female/Child: {{female}} | Dialects: {{dcount}} | Est Value: ${{est}} | Ready for HuggingFace</b></div>

<div class="card">
<h2>➕ Sabon Murya - FULL METADATA (Google/Mozilla Spec)</h2>
<form method="POST" action="/add" enctype="multipart/form-data">
<h3 style="font-size:13px;color:#1e40af">1. WHO - Waye Mai Magana (Speaker)</h3>
<div class="row"><div><label>Sunayen Mai Magana (ko Code - Anonymized)</label><input name="speaker_name" required placeholder="Musa Ibrahim ko SPK_001"></div><div><label>Speaker ID (Auto)</label><input name="speaker_id" placeholder="Auto - SPK_ + lamba"></div></div>
<div class="row3"><div><label>Shekaru</label><input type="number" name="age" min="4" max="95" required></div><div><label>Age Group</label><select name="age_group"><option>Child 4-12 (x3 Value!)</option><option>Teen 13-19 (x2)</option><option>Adult 20-39</option><option>Adult 40-59</option><option>Elder 60+ (x2)</option></select></div><div><label>Jinsi - Mata = x2 Value!</label><select name="gender" required><option>Namiji</option><option>Mace</option><option>Yaro</option><option>Babba</option></select></div></div>
<div class="row"><div><label>Dialect / Yaren Hausa</label><select name="dialect" required>{% for d in dialects %}<option>{{d}}</option>{% endfor %}</select></div><div><label>Education Level</label><select name="education_level"><option>No Formal</option><option>Primary</option><option>Secondary</option><option>University</option><option>Islamiyya</option></select></div></div>
<div class="row"><div><label>Sana'a / Occupation</label><input name="occupation" placeholder="Manomi, Dalibi, Likita, Limami, Dan Kasuwa"></div><div><label>Harsunan da ya iya</label><select name="languages_spoken"><option>Hausa kadai</option><option>Hausa + English</option><option>Hausa + Fulfulde</option><option>Hausa + Larabci</option><option>Hausa + English + Larabci</option></select></div></div>

<h3 style="font-size:13px;color:#1e40af">2. WHERE - Daga ina yake (Location - Abinda kake tambaya)</h3>
<div class="row"><div><label>An haife shi a Jaha - Birth State</label><select name="birth_state">{% for s in states %}<option>{{s}}</option>{% endfor %}</select></div><div><label>Birth LGA</label><input name="birth_lga" placeholder="Ringim"></div></div>
<div class="row"><div><label>Yana zaune a Jaha yanzu - Current State</label><select name="current_state"><option>Jigawa</option>{% for s in states %}<option>{{s}}</option>{% endfor %}</select></div><div><label>Current LGA</label><input name="current_lga" value="Ringim"></div></div>
<div class="row"><div><label>Ward</label><input name="ward" value="Bulangu"></div><div><label>Village / Kauye</label><input name="village" placeholder="Bulangu, Dabi"></div></div>
<div class="row"><div><label>GPS Lat (Optional - idan ya yarda)</label><input name="gps_lat" placeholder="12.3456 - Optional"></div><div><label>GPS Long (Optional)</label><input name="gps_long" placeholder="8.1234 - Optional"></div></div>

<h3 style="font-size:13px;color:#1e40af">3. WHAT - Menene ya fada</h3>
<label>Voice Type - Top 7 da ake bukata</label><select name="voice_type" id="vt" required onchange="loadP()"><option value="">-- Zabi --</option>{% for k,v in vlabels.items() %}<option value="{{k}}">{{v}}</option>{% endfor %}</select>
<div id="pArea"></div>
<label>Transcription - Rubutu 100% daidai da murya (Mozilla Common Voice Requirement)</label><textarea name="transcription" id="tText" required placeholder="Rubuta kalma-kalma abinda ya fada..."></textarea>

<h3 style="font-size:13px;color:#1e40af">4. HOW - Yadda aka dauki</h3>
<div class="row"><div><label>Device Type</label><select name="device_type"><option>Android Phone</option><option>iPhone</option><option>Laptop</option><option>USB Microphone</option><option>Studio Mic</option></select></div><div><label>Device Model</label><input name="device_model" placeholder="Tecno, Infinix, iPhone 12"></div></div>
<div class="row"><div><label>Recording Environment</label><select name="recording_env"><option>Clean Room - Shiru (TTS)</option><option>Kasuwanci - Noisy Market (Real World)</option><option>Gona - Farm</option><option>Gida da Yara - Home</option><option>Mota - Car</option><option>Office</option></select></div><div><label>Noise Level</label><select name="noise_level"><option>Low - Shiru</option><option>Medium</option><option>High - Hayaniya sosai</option></select></div></div>

<h3 style="font-size:13px;color:#1e40af">5. LEGAL - Siyarwa da doka (Consent & License)</h3>
<div class="row"><div><label>License - Inda za a sayar</label><select name="license"><option value="Commercial - AI Training - $$$$">Commercial - AI Training ($$$ - Don Google/OpenAI)</option><option value="CC-BY-4.0 - Common Voice">CC-BY-4.0 - Mozilla Common Voice (Grant)</option><option value="CC-0 - Public Domain">CC-0 - Public Domain</option></select></div><div><label>Payment Type</label><select name="payment_type"><option>Volunteer - Kyauta</option><option>Paid - An biya</option><option>Future Revenue Share</option></select></div></div>
<div class="row"><div><label>Payment Amount (Naira)</label><input name="payment_amount" placeholder="500, 1000, 0"></div><div><label>Collector - Wanda ya tattara</label><input name="collector_name" value="Bulangu AI Lab"></div></div>
<label><input type="checkbox" name="consent" required> ✅ NA YARDA - I consent to sell my voice for AI training, commercial use, worldwide, including Google, Meta, OpenAI, Mozilla. Na karba hakki na. (Mozilla & Google Requirement)</label>

<label>Audio File - WAV 16kHz 16bit (Best) ko MP3</label><input type="file" name="audio" accept="audio/*" required>
<button class="btn btn-p" style="width:100%;margin-top:12px">💾 SAVE - Add to Global Voice Bank</button>
</form>
</div>

<div class="card">
<h2>📊 Export - Ready for Buyers</h2>
<a href="/export/csv" class="btn btn-d">📥 metadata.csv (Full)</a> <a href="/export/commonvoice" class="btn btn-p">🎤 Mozilla Common Voice TSV</a> <a href="/export/huggingface" class="btn btn-s">🤗 HuggingFace JSONL</a> <a href="/export/zip" class="btn btn-s">📦 ALL Audios ZIP</a>
<div style="overflow:auto;margin-top:10px"><table><tr><th>ID</th><th>Speaker/Location</th><th>Age/Gender/Dialect</th><th>Type</th><th>Text</th><th>Audio</th></tr>
{% for r in rows %}<tr><td>{{r[0]}}</td><td>{{r[2]}}<br><small>{{r[10]}}/{{r[11]}}/{{r[12]}} - {{r[13]}}</small></td><td>{{r[3]}}/{{r[5]}}<br>{{r[6]}}</td><td>{{r[20]}}</td><td>{{r[23][:50]}}</td><td><audio controls src="/audio/{{r[0]}}" style="width:150px"></audio></td></tr>{% endfor %}</table></div>
</div>
</div><script>
const prompts = {{prompts_json|safe}};
function loadP(){const vt=document.getElementById('vt').value;const a=document.getElementById('pArea');if(!vt){a.innerHTML='';return;}let h='<label>Prompt Library - Danna ka zaba:</label>';prompts[vt].forEach(p=>{h+=`<div class="prompt-box" onclick="document.getElementById('tText').value=this.innerText">${p}</div>`});a.innerHTML=h;}
</script></body></html>
"""

@app.route('/')
def home():
    if 'user' not in session: return redirect('/login')
    conn=sqlite3.connect(DB_PATH);c=conn.cursor();c.execute("SELECT * FROM voices ORDER BY created_at DESC");rows=c.fetchall();total=len(rows);female=len([r for r in rows if 'Mace' in str(r[5]) or 'Yaro' in str(r[5]) or 'Child' in str(r[4])]);dcount=len(set([r[6] for r in rows]));est=round(total*0.7*35);conn.close()
    return render_template_string(HTML, rows=rows,total=total,female=female,dcount=dcount,est=est,dialects=DIALECTS,states=STATES,vlabels=VOICE_LABELS,prompts_json=json.dumps(PROMPTS))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=request.form['username'];p=request.form['password'];conn=sqlite3.connect(DB_PATH);c=conn.cursor();c.execute("SELECT * FROM users WHERE username=?",(u,));user=c.fetchone();conn.close()
        if user and check_password_hash(user[2],p): session['user']=u;return redirect('/')
        return "Login failed - Bulangu / Bulangu123"
    return '<form method="POST" style="max-width:400px;margin:80px auto;padding:20px;border:1px solid #ccc;border-radius:12px"><h2>V9.1 Login</h2><input name="username" placeholder="Bulangu" style="width:100%;padding:10px;margin:6px 0"><br><input type="password" name="password" placeholder="Bulangu123" style="width:100%;padding:10px;margin:6px 0"><br><button style="width:100%;padding:10px;background:#2563eb;color:#fff;border:0;border-radius:8px">Login</button></form>'

@app.route('/add', methods=['POST'])
def add():
    if 'user' not in session: return redirect('/login')
    f=request.files.get('audio');id_=str(uuid.uuid4())[:8];ext=secure_filename(f.filename).split('.')[-1] if '.' in f.filename else 'mp3';filename=f"{id_}.{ext}";path=os.path.join(UPLOAD_FOLDER,filename);f.save(path)
    conn=sqlite3.connect(DB_PATH);c=conn.cursor()
    c.execute("INSERT INTO voices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (id_, request.form.get('speaker_id') or f"SPK_{id_}", request.form.get('speaker_name'), request.form.get('age'), request.form.get('age_group'), request.form.get('gender'), request.form.get('dialect'),
     request.form.get('birth_state'), request.form.get('birth_lga'), request.form.get('current_state'), request.form.get('current_lga'), request.form.get('ward'), request.form.get('village'),
     request.form.get('gps_lat'), request.form.get('gps_long'), request.form.get('education_level'), request.form.get('occupation'), request.form.get('languages_spoken'), '', '',
     request.form.get('voice_type'), '', request.form.get('transcription',''), request.form.get('transcription'), filename, 0, '16kHz', ext,
     request.form.get('device_type'), request.form.get('device_model'), request.form.get('recording_env'), request.form.get('noise_level'), '5',
     1, datetime.now().isoformat(), request.form.get('license'), request.form.get('payment_type'), request.form.get('payment_amount'), request.form.get('collector_name'), datetime.now().isoformat()))
    conn.commit(); conn.close();return redirect('/')

@app.route('/audio/<id_>')
def aud(id_):
    conn=sqlite3.connect(DB_PATH);c=conn.cursor();c.execute("SELECT audio_filename FROM voices WHERE id=?",(id_,));r=c.fetchone();conn.close()
    return send_file(os.path.join(UPLOAD_FOLDER,r[0])) if r else ("Not found",404)

@app.route('/export/csv')
def exp_csv():
    conn=sqlite3.connect(DB_PATH);c=conn.cursor();c.execute("SELECT * FROM voices");rows=c.fetchall();conn.close();si=io.StringIO();w=csv.writer(si)
    w.writerow(['id','speaker_id','speaker_name','age','age_group','gender','dialect','birth_state','birth_lga','current_state','current_lga','ward','village','gps_lat','gps_long','education','occupation','languages','voice_type','transcription','audio','device','recording_env','noise','license','payment','collector','created_at'])
    for r in rows: w.writerow([r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],r[9],r[10],r[11],r[12],r[13],r[14],r[15],r[16],r[17],r[20],r[23],r[24],r[27],r[29],r[30],r[33],r[35],r[36],r[37]])
    return Response(si.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment;filename=bulangu_FULL_metadata_google_mozilla.csv'})

@app.route('/export/commonvoice')
def exp_cv():
    conn=sqlite3.connect(DB_PATH);c=conn.cursor();c.execute("SELECT * FROM voices");rows=c.fetchall();conn.close();si=io.StringIO();w=csv.writer(si, delimiter='\t')
    w.writerow(['client_id','path','sentence','up_votes','down_votes','age','gender','accent','locale','segment'])
    for r in rows: w.writerow([r[1], r[24], r[23], 2, 0, r[3], r[5], r[6], 'ha', ''])
    return Response(si.getvalue(), mimetype='text/tab-separated-values', headers={'Content-Disposition':'attachment;filename=ha_commonvoice.tsv'})

@app.route('/export/huggingface')
def exp_hf():
    conn=sqlite3.connect(DB_PATH);c=conn.cursor();c.execute("SELECT * FROM voices");rows=c.fetchall();conn.close();lines=[]
    for r in rows: lines.append(json.dumps({"audio":r[24],"text":r[23],"speaker_id":r[1],"age":r[3],"gender":r[5],"dialect":r[6],"accent":r[6],"birthplace":f"{r[7]}/{r[8]}","current_location":f"{r[9]}/{r[10]}/{r[11]}/{r[12]}","gps":f"{r[13]},{r[14]}","education":r[15],"occupation":r[16],"languages":r[17],"voice_type":r[20],"device":r[27],"environment":r[29],"license":r[33]}, ensure_ascii=False))
    return Response("\n".join(lines), mimetype='application/jsonl', headers={'Content-Disposition':'attachment;filename=dataset.jsonl'})

@app.route('/export/zip')
def exp_zip():
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,'w') as z:
        for root,_,files in os.walk(UPLOAD_FOLDER):
            for file in files: z.write(os.path.join(root,file), file)
    mem.seek(0);return send_file(mem, as_attachment=True, download_name='bulangu_full_audios.zip')

if __name__=='__main__': app.run()
