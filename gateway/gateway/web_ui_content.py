"""Static dashboard templates and docs for NiFi web UI."""

from __future__ import annotations

# ── Translations ────────────────────────────────────────────────────
_T = {
    "ru": {
        "title": "nifi-mcp-universal",
        "subtitle": "MCP-шлюз для Apache NiFi",
        "h_connections": "Подключения NiFi",
        "h_add_conn": "Новое подключение",
        "h_edit_conn": "Редактирование",
        "conn_name": "Имя соединения",
        "nifi_url": "NiFi API URL",
        "auth_method": "Метод аутентификации",
        "certificate": "Сертификат (.p12)",
        "cert_key": "Ключ (.key)",
        "cert_password": "Пароль сертификата",
        "knox_token": "Knox JWT Token",
        "knox_cookie": "Knox Cookie",
        "knox_passcode": "Knox Passcode",
        "knox_user": "Логин",
        "knox_password": "Пароль",
        "knox_gateway_url": "Knox Gateway URL",
        "verify_ssl": "Проверять SSL",
        "allow_write": "Разрешить запись",
        "default_conn": "По умолчанию",
        "btn_connect": "Подключить",
        "btn_test": "Тест",
        "btn_save": "Сохранить",
        "btn_cancel": "Отмена",
        "btn_refresh": "Обновить",
        "btn_edit": "Изменить",
        "btn_delete": "Удалить",
        "btn_docs": "Документация",
        "connected": "Подключено",
        "disconnected": "Отключено",
        "rw": "Чтение/Запись",
        "ro": "Только чтение",
        "no_connections": "Нет подключений. Добавьте первое.",
        "confirm_delete": "Удалить соединение",
        "confirm_delete_text": "Вы уверены? Соединение будет разорвано.",
        "fill_fields": "Заполните обязательные поля: имя и URL",
        "msg_connected": "Подключено",
        "msg_disconnected": "Отключено",
        "msg_saved": "Сохранено",
        "msg_default_set": "Установлено по умолчанию",
        "msg_error": "Ошибка",
        "auth_prompt": "Введите Bearer token для Dashboard API",
        "msg_test_ok": "Соединение успешно",
        "msg_test_fail": "Ошибка соединения",
        "auth_none": "Без аутентификации",
        "auth_cert_p12": "Сертификат (P12)",
        "auth_cert_pem": "Сертификат (PEM)",
        "auth_knox_token": "Knox JWT Token",
        "auth_knox_cookie": "Knox Cookie",
        "auth_knox_passcode": "Knox Passcode",
        "auth_basic": "Логин/Пароль",
    },
    "en": {
        "title": "nifi-mcp-universal",
        "subtitle": "MCP gateway for Apache NiFi",
        "h_connections": "NiFi Connections",
        "h_add_conn": "New Connection",
        "h_edit_conn": "Edit Connection",
        "conn_name": "Connection Name",
        "nifi_url": "NiFi API URL",
        "auth_method": "Auth Method",
        "certificate": "Certificate (.p12)",
        "cert_key": "Key (.key)",
        "cert_password": "Certificate Password",
        "knox_token": "Knox JWT Token",
        "knox_cookie": "Knox Cookie",
        "knox_passcode": "Knox Passcode",
        "knox_user": "Username",
        "knox_password": "Password",
        "knox_gateway_url": "Knox Gateway URL",
        "verify_ssl": "Verify SSL",
        "allow_write": "Allow write",
        "default_conn": "Default",
        "btn_connect": "Connect",
        "btn_test": "Test",
        "btn_save": "Save",
        "btn_cancel": "Cancel",
        "btn_refresh": "Refresh",
        "btn_edit": "Edit",
        "btn_delete": "Delete",
        "btn_docs": "Docs",
        "connected": "Connected",
        "disconnected": "Disconnected",
        "rw": "Read/Write",
        "ro": "Read-only",
        "no_connections": "No connections. Add your first one.",
        "confirm_delete": "Delete connection",
        "confirm_delete_text": "Are you sure? The connection will be closed.",
        "fill_fields": "Fill required fields: name and URL",
        "msg_connected": "Connected",
        "msg_disconnected": "Disconnected",
        "msg_saved": "Saved",
        "msg_default_set": "Set as default",
        "msg_error": "Error",
        "auth_prompt": "Enter Bearer token for Dashboard API",
        "msg_test_ok": "Connection successful",
        "msg_test_fail": "Connection failed",
        "auth_none": "No Auth",
        "auth_cert_p12": "Certificate (P12)",
        "auth_cert_pem": "Certificate (PEM)",
        "auth_knox_token": "Knox JWT Token",
        "auth_knox_cookie": "Knox Cookie",
        "auth_knox_passcode": "Knox Passcode",
        "auth_basic": "Username/Password",
    },
}

# ── HTML ────────────────────────────────────────────────────────────
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="{{lang}}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>nifi-mcp-universal</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#f8fafc;height:100vh;display:flex;flex-direction:column;overflow:hidden}
.content{flex:1;overflow-y:auto}

/* ── Header ── */
.header{background:#1e293b;border-bottom:1px solid #334155;padding:8px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;flex-shrink:0}
.header-left{display:flex;align-items:center;gap:10px}
.header h1{font-size:1.05rem;color:#f8fafc;font-weight:700}
.header .sub{color:#64748b;font-size:.75rem}
.header-right{display:flex;align-items:center;gap:6px;flex-wrap:wrap}

/* ── Language switcher ── */
.lang-sw{display:flex;border:1px solid #475569;border-radius:5px;overflow:hidden}
.lang-sw a{padding:3px 8px;font-size:.7rem;color:#94a3b8;display:block;text-decoration:none}
.lang-sw a.on{background:#334155;color:#f8fafc}

/* ── Buttons ── */
.btn{display:inline-flex;align-items:center;gap:4px;padding:5px 12px;border-radius:5px;font-size:.78rem;cursor:pointer;border:1px solid #475569;background:#1e293b;color:#94a3b8;text-decoration:none;transition:.15s}
.btn:hover{background:#334155;color:#f8fafc}
.btn svg{width:13px;height:13px}
.btn-p{background:#0369a1;border-color:#0369a1;color:#fff}
.btn-p:hover{background:#0284c7}
.btn-d{color:#ef4444;border-color:rgba(239,68,68,.25)}
.btn-d:hover{background:rgba(239,68,68,.1);color:#ef4444;border-color:#ef4444}
.btn-ds{background:#991b1b;border-color:#991b1b;color:#fff}
.btn-ds:hover{background:#b91c1c}

/* ── Content ── */
.content{padding:20px}

/* ── Card ── */
.card{background:#1e293b;border-radius:8px;padding:12px;border:1px solid #334155;overflow:hidden;margin-bottom:14px}
.card h2{font-size:.65rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;font-weight:600}

/* ── Connection Item ── */
.db-item{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:10px 12px;margin-bottom:8px;transition:border-color .15s}
.db-item:last-child{margin-bottom:0}
.db-item:hover{border-color:#475569}
.db-row{display:flex;align-items:center;gap:10px}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot.ok{background:#22c55e}
.dot.err{background:#ef4444}
.db-info{flex:1;min-width:0}
.db-name{font-weight:600;font-size:.88rem}
.db-details{color:#64748b;font-size:.75rem;font-family:'SF Mono','Cascadia Code',monospace;margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.db-badges{display:flex;gap:5px;margin-top:4px;flex-wrap:wrap}
.db-actions{display:flex;gap:4px;flex-shrink:0}

/* ── Badges ── */
.badge{display:inline-flex;align-items:center;padding:1px 6px;border-radius:3px;font-size:.62rem;font-weight:600}
.badge-g{background:rgba(34,197,94,.12);color:#22c55e}
.badge-r{background:rgba(239,68,68,.12);color:#ef4444}
.badge-b{background:rgba(59,130,246,.12);color:#3b82f6}
.badge-c{background:#164e63;color:#22d3ee}

/* ── Default toggle ── */
.rd{display:flex;align-items:center;gap:5px;cursor:pointer;font-size:.72rem;color:#94a3b8}
.rd:hover{color:#cbd5e1}
.rb{width:14px;height:14px;border-radius:50%;border:2px solid #475569;display:flex;align-items:center;justify-content:center;transition:.15s;flex-shrink:0}
.rb.on{border-color:#22d3ee}
.rb.on::after{content:'';width:7px;height:7px;border-radius:50%;background:#22d3ee}
.rd:hover .rb{border-color:#22d3ee}

/* ── Toggle switch ── */
.toggle{display:flex;align-items:center;gap:8px;cursor:pointer;font-size:.78rem;color:#cbd5e1;user-select:none}
.toggle input{display:none}
.toggle-track{width:34px;height:18px;border-radius:9px;background:#475569;position:relative;transition:.2s;flex-shrink:0}
.toggle-track::after{content:'';width:14px;height:14px;border-radius:50%;background:#94a3b8;position:absolute;top:2px;left:2px;transition:.2s}
.toggle input:checked+.toggle-track{background:#22c55e}
.toggle input:checked+.toggle-track::after{left:18px;background:#fff}

/* ── Form ── */
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.form-group{display:flex;flex-direction:column;gap:3px}
.form-group.full{grid-column:1/-1}
.form-group label{font-size:.65rem;color:#64748b;text-transform:uppercase;letter-spacing:.04em;font-weight:600}
input[type="file"]{padding:4px 8px;font-size:.75rem}
input[type="file"]::file-selector-button{padding:3px 10px;border-radius:4px;border:1px solid #475569;background:#1e293b;color:#94a3b8;font-size:.75rem;cursor:pointer;margin-right:8px;transition:.15s}
input[type="file"]::file-selector-button:hover{background:#334155;color:#f8fafc}
input,select,textarea{padding:5px 8px;border-radius:4px;border:1px solid #475569;background:#0f172a;color:#e2e8f0;font-size:.8rem;transition:border .15s;width:100%;font-family:inherit;-moz-appearance:textfield}
input::-webkit-outer-spin-button,input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}
input:focus,select:focus,textarea:focus{outline:none;border-color:#38bdf8}
select{cursor:pointer}
textarea{resize:vertical;min-height:40px}
.form-actions{display:flex;gap:6px;justify-content:flex-end;margin-top:10px}

/* ── Empty state ── */
.empty{text-align:center;padding:20px;color:#64748b;font-size:.82rem}

/* ── Overlay ── */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100;display:flex;align-items:center;justify-content:center}
.modal{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;width:520px;max-width:92%}
.modal h3{font-size:.88rem;margin-bottom:14px;color:#f8fafc}
.modal-actions{display:flex;gap:6px;justify-content:flex-end;margin-top:14px}

/* ── Toast ── */
.toast-msg{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#164e63;color:#22d3ee;padding:14px 24px;border-radius:8px;font-size:.9rem;z-index:999;max-width:500px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.5);pointer-events:none}
.toast-err{background:#7f1d1d;color:#fca5a5}

/* ── Scrollbar ── */
.content::-webkit-scrollbar{width:8px}
.content::-webkit-scrollbar-track{background:#0f172a}
.content::-webkit-scrollbar-thumb{background:#334155;border-radius:4px}
.content::-webkit-scrollbar-thumb:hover{background:#475569}
.content{scrollbar-width:thin;scrollbar-color:#334155 #0f172a}

/* ── Two-column ── */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}

/* ── Footer ── */
.footer{padding:8px 20px;text-align:center;color:#475569;font-size:.68rem;border-top:1px solid #1e293b;flex-shrink:0}
.footer a{color:#64748b;text-decoration:none}.footer a:hover{color:#94a3b8}

/* ── Auth fields ── */
.auth-fields{display:none}
.auth-fields.active{display:contents}

@media(max-width:900px){
  .cols{grid-template-columns:1fr}
}
@media(max-width:600px){
  .content{padding:10px}
  .form-grid{grid-template-columns:1fr}
  .db-row{flex-wrap:wrap}
  .db-actions{width:100%;justify-content:flex-end}
}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div><h1>nifi-mcp-universal</h1><span class="sub">{{subtitle}}</span></div>
  </div>
  <div class="header-right">
    <div class="lang-sw">
      <a href="?lang=ru" class="{{ru_on}}">RU</a>
      <a href="?lang=en" class="{{en_on}}">EN</a>
    </div>
    <a class="btn" href="/dashboard/docs?lang={{lang}}" target="_blank">{{btn_docs}}</a>
    <button class="btn" onclick="loadConns()">{{btn_refresh}}</button>
  </div>
</div>

<div class="content">
<div class="cols">

  <!-- ── Connection list ── -->
  <div class="card">
    <h2>{{h_connections}}</h2>
    <div id="conn-list"></div>
  </div>

  <!-- ── Add connection form ── -->
  <div class="card" id="add-card">
    <h2>{{h_add_conn}}</h2>
    <div class="form-grid">
      <div class="form-group">
        <label>{{conn_name}} *</label>
        <input id="f-name">
      </div>
      <div class="form-group">
        <label>{{nifi_url}} *</label>
        <input id="f-url" placeholder="https://nifi.example.com/nifi-api">
      </div>
      <div class="form-group full">
        <label>{{auth_method}}</label>
        <select id="f-auth" onchange="toggleAuth()">
          <option value="none">{{auth_none}}</option>
          <option value="certificate_p12">{{auth_cert_p12}}</option>
          <option value="certificate_pem">{{auth_cert_pem}}</option>
          <option value="knox_token">{{auth_knox_token}}</option>
          <option value="knox_cookie">{{auth_knox_cookie}}</option>
          <option value="knox_passcode">{{auth_knox_passcode}}</option>
          <option value="basic">{{auth_basic}}</option>
        </select>
      </div>

      <!-- P12 -->
      <div class="auth-fields" id="af-certificate_p12">
        <div class="form-group"><label>{{certificate}}</label><input id="f-cert" type="file" accept=".p12,.pfx"></div>
        <div class="form-group"><label>{{cert_password}}</label><input id="f-certpw" type="password"></div>
      </div>
      <!-- PEM -->
      <div class="auth-fields" id="af-certificate_pem">
        <div class="form-group"><label>{{certificate}} (.pem/.crt)</label><input id="f-pemcert" type="file" accept=".pem,.crt"></div>
        <div class="form-group"><label>{{cert_key}}</label><input id="f-pemkey" type="file" accept=".key,.pem"></div>
      </div>
      <!-- Knox Token -->
      <div class="auth-fields" id="af-knox_token">
        <div class="form-group full"><label>{{knox_token}}</label><textarea id="f-ktoken" rows="2"></textarea></div>
      </div>
      <!-- Knox Cookie -->
      <div class="auth-fields" id="af-knox_cookie">
        <div class="form-group full"><label>{{knox_cookie}}</label><textarea id="f-kcookie" rows="2"></textarea></div>
      </div>
      <!-- Knox Passcode -->
      <div class="auth-fields" id="af-knox_passcode">
        <div class="form-group"><label>{{knox_passcode}}</label><textarea id="f-kpass" rows="2"></textarea></div>
        <div class="form-group"><label>{{knox_gateway_url}}</label><input id="f-kgw1"></div>
      </div>
      <!-- Basic -->
      <div class="auth-fields" id="af-basic">
        <div class="form-group"><label>{{knox_user}}</label><input id="f-user"></div>
        <div class="form-group"><label>{{knox_password}}</label><input id="f-pass" type="password"></div>
        <div class="form-group full"><label>{{knox_gateway_url}}</label><input id="f-kgw2"></div>
      </div>

      <div class="form-group" style="margin-top:2px">
        <label class="toggle">
          <input type="checkbox" id="f-ssl" checked>
          <span class="toggle-track"></span>
          {{verify_ssl}}
        </label>
      </div>
      <div class="form-group" style="margin-top:2px">
        <label class="toggle">
          <input type="checkbox" id="f-aw">
          <span class="toggle-track"></span>
          {{allow_write}}
        </label>
      </div>
    </div>
    <div class="form-actions">
      <button class="btn" onclick="testConn()">{{btn_test}}</button>
      <button class="btn" onclick="connectNifi()">&#8594; {{btn_connect}}</button>
    </div>
  </div>

</div>
</div>

<script>
const T = {{t_json}};
const _API_KEY_STORAGE = 'nifi_mcp_dashboard_api_key';
let _API_KEY = sessionStorage.getItem(_API_KEY_STORAGE) || '';
const AUTH_METHODS = ['none','certificate_p12','certificate_pem','knox_token','knox_cookie','knox_passcode','basic'];

function toast(msg, isErr) {
  var d = document.createElement('div');
  d.className = 'toast-msg' + (isErr ? ' toast-err' : '');
  d.textContent = msg;
  document.body.appendChild(d);
  setTimeout(function(){ d.remove() }, 3000);
}

async function api(url, opts, retryAuth) {
  try {
    opts = opts || {};
    if (typeof retryAuth === 'undefined') retryAuth = true;
    var headers = Object.assign({}, opts.headers || {});
    if (_API_KEY) {
      headers['Authorization'] = 'Bearer ' + _API_KEY;
    }
    const r = await fetch(url, Object.assign({}, opts, {headers: headers}));
    if (r.status === 401) {
      if (retryAuth) {
        const entered = window.prompt(T.auth_prompt || 'Enter Bearer token');
        if (entered && entered.trim()) {
          _API_KEY = entered.trim();
          sessionStorage.setItem(_API_KEY_STORAGE, _API_KEY);
          return api(url, opts, false);
        }
      }
      toast(T.msg_error + ': unauthorized', true);
      return null;
    }
    return await r.json();
  } catch(e) { toast(T.msg_error + ': ' + e.message, true); return null; }
}

/* ═══ XSS PROTECTION ═══ */
function escHtml(s) {
  var d = document.createElement('div');
  d.appendChild(document.createTextNode(s || ''));
  return d.innerHTML;
}
function escAttr(s) {
  return escHtml(s).replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

function toggleAuth(prefix) {
  prefix = prefix || 'f';
  var sel = document.getElementById(prefix === 'f' ? 'f-auth' : 'e-auth');
  var method = sel.value;
  var container = sel.closest('.form-grid') || sel.closest('.modal');
  container.querySelectorAll('.auth-fields').forEach(function(el) {
    el.classList.remove('active');
  });
  var target = container.querySelector('#' + (prefix === 'f' ? 'af-' : 'eaf-') + method);
  if (target) target.classList.add('active');
  // Auto-uncheck SSL verify for certificate auth (self-signed certs are typical for NiFi)
  var sslCheckbox = document.getElementById(prefix === 'f' ? 'f-ssl' : 'e-ssl');
  if (sslCheckbox && (method === 'certificate_p12' || method === 'certificate_pem')) {
    sslCheckbox.checked = false;
  }
}

function authLabel(method) {
  return T['auth_' + method.replace('certificate_','cert_').replace('knox_','')] || method;
}

/* ═══ LOAD CONNECTIONS ═══ */
async function loadConns() {
  const [conns, status] = await Promise.all([api('/api/connections'), api('/api/status')]);
  const list = document.getElementById('conn-list');
  const activeConn = status?.active_default || '';

  if (!conns || conns.length === 0) {
    list.innerHTML = '<div class="empty">' + T.no_connections + '</div>';
    return;
  }

  list.innerHTML = conns.map(function(c) {
    var isDefault = c.name === activeConn;
    var eName = escHtml(c.name);
    var eUrl = escHtml(c.url);
    var eNameAttr = escAttr(c.name);
    return '<div class="db-item">' +
      '<div class="db-row">' +
        '<div class="dot ' + (c.connected ? 'ok' : 'err') + '"></div>' +
        '<div class="db-info">' +
          '<div class="db-name">' + eName + '</div>' +
          '<div class="db-details">' + eUrl + '</div>' +
          '<div class="db-badges">' +
            '<span class="badge ' + (c.connected ? 'badge-g' : 'badge-r') + '">' +
              (c.connected ? T.connected : T.disconnected) + '</span>' +
            (c.nifi_version ? '<span class="badge badge-b">NiFi ' + escHtml(c.nifi_version) + '</span>' : '') +
            '<span class="badge badge-c">' + (c.readonly ? T.ro : T.rw) + '</span>' +
          '</div>' +
        '</div>' +
        '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">' +
          '<div class="rd" onclick="setDefault(\'' + eNameAttr + '\')">' +
            '<div class="rb ' + (isDefault ? 'on' : '') + '"></div>' +
            '<span>' + T.default_conn + '</span>' +
          '</div>' +
          '<div class="db-actions">' +
            '<button class="btn" onclick="editConn(\'' + eNameAttr + '\')">' + T.btn_edit + '</button>' +
            '<button class="btn btn-d" onclick="confirmDelete(\'' + eNameAttr + '\')">' + T.btn_delete + '</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

/* ═══ CONNECT ═══ */
async function connectNifi() {
  var name = document.getElementById('f-name').value.trim();
  var url  = document.getElementById('f-url').value.trim();
  var auth = document.getElementById('f-auth').value;
  if (!name || !url) { toast(T.fill_fields, true); return; }

  var form = new FormData();
  form.append('name', name);
  form.append('url', url);
  form.append('auth_method', auth);
  form.append('verify_ssl', document.getElementById('f-ssl').checked ? 'true' : 'false');
  form.append('readonly', document.getElementById('f-aw').checked ? 'false' : 'true');

  if (auth === 'certificate_p12') {
    var cf = document.getElementById('f-cert').files[0];
    if (cf) form.append('cert_file', cf);
    form.append('cert_password', document.getElementById('f-certpw').value);
  } else if (auth === 'certificate_pem') {
    var pf = document.getElementById('f-pemcert').files[0];
    if (pf) form.append('cert_file', pf);
    var kf = document.getElementById('f-pemkey').files[0];
    if (kf) form.append('key_file', kf);
  } else if (auth === 'knox_token') {
    form.append('knox_token', document.getElementById('f-ktoken').value);
  } else if (auth === 'knox_cookie') {
    form.append('knox_cookie', document.getElementById('f-kcookie').value);
  } else if (auth === 'knox_passcode') {
    form.append('knox_passcode', document.getElementById('f-kpass').value);
    form.append('knox_gateway_url', document.getElementById('f-kgw1').value);
  } else if (auth === 'basic') {
    form.append('knox_user', document.getElementById('f-user').value);
    form.append('knox_password', document.getElementById('f-pass').value);
    form.append('knox_gateway_url', document.getElementById('f-kgw2').value);
  }

  var j = await api('/api/connect', { method: 'POST', body: form });
  if (!j || j.error) { toast(T.msg_error + ': ' + (j?.error || 'unknown'), true); return; }
  toast(T.msg_connected + ': ' + name);
  document.getElementById('f-name').value = '';
  document.getElementById('f-url').value = '';
  document.getElementById('f-auth').value = 'none';
  toggleAuth();
  loadConns();
}

/* ═══ TEST ═══ */
async function testConn() {
  var url = document.getElementById('f-url').value.trim();
  var auth = document.getElementById('f-auth').value;
  if (!url) { toast(T.fill_fields, true); return; }

  var opts;
  if (auth === 'certificate_p12' || auth === 'certificate_pem') {
    var form = new FormData();
    form.append('url', url);
    form.append('auth_method', auth);
    form.append('verify_ssl', document.getElementById('f-ssl').checked ? 'true' : 'false');
    if (auth === 'certificate_p12') {
      var cf = document.getElementById('f-cert').files[0];
      if (cf) form.append('cert_file', cf);
      form.append('cert_password', document.getElementById('f-certpw').value);
    } else {
      var pf = document.getElementById('f-pemcert').files[0];
      if (pf) form.append('cert_file', pf);
      var kf = document.getElementById('f-pemkey').files[0];
      if (kf) form.append('key_file', kf);
    }
    opts = { method: 'POST', body: form };
  } else {
    var body = { url: url, auth_method: auth, verify_ssl: document.getElementById('f-ssl').checked };
    if (auth === 'knox_token') body.knox_token = document.getElementById('f-ktoken').value;
    else if (auth === 'knox_cookie') body.knox_cookie = document.getElementById('f-kcookie').value;
    else if (auth === 'knox_passcode') { body.knox_passcode = document.getElementById('f-kpass').value; body.knox_gateway_url = document.getElementById('f-kgw1').value; }
    else if (auth === 'basic') { body.knox_user = document.getElementById('f-user').value; body.knox_password = document.getElementById('f-pass').value; body.knox_gateway_url = document.getElementById('f-kgw2').value; }
    opts = { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) };
  }

  var r = await api('/api/test', opts);
  if (r && r.ok) { toast(T.msg_test_ok + ' — NiFi ' + (r.nifi_version||'?')); }
  else { toast(T.msg_test_fail + ': ' + (r?.error || '?'), true); }
}

/* ═══ SET DEFAULT ═══ */
async function setDefault(name) {
  var r = await api('/api/switch', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name}) });
  if (r && r.error) { toast(T.msg_error + ': ' + r.error, true); return; }
  toast(T.msg_default_set + ': ' + name);
  loadConns();
}

/* ═══ EDIT (modal) ═══ */
async function editConn(name) {
  var conns = await api('/api/connections');
  var c = conns.find(function(x){ return x.name === name; });
  if (!c) return;

  var ov = document.createElement('div');
  ov.className = 'overlay';
  ov.innerHTML =
    '<div class="modal">' +
      '<h3>' + T.h_edit_conn + '</h3>' +
      '<div class="form-grid">' +
        '<div class="form-group"><label>' + T.conn_name + '</label><input id="e-name" value="' + escAttr(c.name) + '"></div>' +
        '<div class="form-group"><label>' + T.nifi_url + '</label><input id="e-url" value="' + escAttr(c.url) + '"></div>' +
        '<div class="form-group full"><label>' + T.auth_method + '</label><select id="e-auth" onchange="toggleAuth(\'e\')">' +
          AUTH_METHODS.map(function(m){ return '<option value="'+m+'"'+(c.auth_method===m?' selected':'')+'>'+authLabel(m)+'</option>'; }).join('') +
        '</select></div>' +
        /* P12 */
        '<div class="auth-fields" id="eaf-certificate_p12">' +
          '<div class="form-group"><label>' + T.certificate + '</label><input id="e-cert" type="file" accept=".p12,.pfx">' + (c.cert_path ? '<span style="font-size:.7rem;color:#64748b;margin-top:2px">' + escHtml(c.cert_path) + '</span>' : '') + '</div>' +
          '<div class="form-group"><label>' + T.cert_password + '</label><input id="e-certpw" type="password" placeholder="' + (c.cert_password === '***' ? '••••••' : '') + '"></div>' +
        '</div>' +
        /* PEM */
        '<div class="auth-fields" id="eaf-certificate_pem">' +
          '<div class="form-group"><label>' + T.certificate + ' (.pem/.crt)</label><input id="e-pemcert" type="file" accept=".pem,.crt">' + (c.cert_path ? '<span style="font-size:.7rem;color:#64748b;margin-top:2px">' + escHtml(c.cert_path) + '</span>' : '') + '</div>' +
          '<div class="form-group"><label>' + T.cert_key + '</label><input id="e-pemkey" type="file" accept=".key,.pem">' + (c.cert_key_path ? '<span style="font-size:.7rem;color:#64748b;margin-top:2px">' + escHtml(c.cert_key_path) + '</span>' : '') + '</div>' +
        '</div>' +
        /* Knox Token */
        '<div class="auth-fields" id="eaf-knox_token">' +
          '<div class="form-group full"><label>' + T.knox_token + '</label><textarea id="e-ktoken" rows="2">' + (c.knox_token !== '***' ? escHtml(c.knox_token||'') : '') + '</textarea></div>' +
        '</div>' +
        /* Knox Cookie */
        '<div class="auth-fields" id="eaf-knox_cookie">' +
          '<div class="form-group full"><label>' + T.knox_cookie + '</label><textarea id="e-kcookie" rows="2">' + (c.knox_cookie !== '***' ? escHtml(c.knox_cookie||'') : '') + '</textarea></div>' +
        '</div>' +
        /* Knox Passcode */
        '<div class="auth-fields" id="eaf-knox_passcode">' +
          '<div class="form-group"><label>' + T.knox_passcode + '</label><textarea id="e-kpass" rows="2">' + (c.knox_passcode !== '***' ? escHtml(c.knox_passcode||'') : '') + '</textarea></div>' +
          '<div class="form-group"><label>' + T.knox_gateway_url + '</label><input id="e-kgw1" value="' + escAttr(c.knox_gateway_url||'') + '"></div>' +
        '</div>' +
        /* Basic */
        '<div class="auth-fields" id="eaf-basic">' +
          '<div class="form-group"><label>' + T.knox_user + '</label><input id="e-user" value="' + escAttr(c.knox_user||'') + '"></div>' +
          '<div class="form-group"><label>' + T.knox_password + '</label><input id="e-pass" type="password" placeholder="' + (c.knox_password === '***' ? '••••••' : '') + '"></div>' +
          '<div class="form-group full"><label>' + T.knox_gateway_url + '</label><input id="e-kgw2" value="' + escAttr(c.knox_gateway_url||'') + '"></div>' +
        '</div>' +
        '<div class="form-group" style="margin-top:2px"><label class="toggle"><input type="checkbox" id="e-ssl" '+(c.verify_ssl?'checked':'')+'><span class="toggle-track"></span>' + T.verify_ssl + '</label></div>' +
        '<div class="form-group" style="margin-top:2px"><label class="toggle"><input type="checkbox" id="e-aw" '+(!c.readonly?'checked':'')+'><span class="toggle-track"></span>' + T.allow_write + '</label></div>' +
      '</div>' +
      '<div class="modal-actions">' +
        '<button class="btn" onclick="this.closest(\'.overlay\').remove()">' + T.btn_cancel + '</button>' +
        '<button class="btn" onclick="saveEdit(\'' + escAttr(name) + '\')">' + T.btn_save + '</button>' +
      '</div>' +
    '</div>';

  document.body.appendChild(ov);
  toggleAuth('e');
  ov.addEventListener('click', function(e) { if (e.target === ov) ov.remove(); });
}

async function saveEdit(oldName) {
  var newName = document.getElementById('e-name').value.trim();
  var url = document.getElementById('e-url').value.trim();
  var auth = document.getElementById('e-auth').value;
  var ssl = document.getElementById('e-ssl').checked;
  var aw = document.getElementById('e-aw').checked;

  if (!newName || !url) { toast(T.fill_fields, true); return; }

  var form = new FormData();
  form.append('old_name', oldName);
  form.append('name', newName);
  form.append('url', url);
  form.append('auth_method', auth);
  form.append('verify_ssl', ssl ? 'true' : 'false');
  form.append('readonly', aw ? 'false' : 'true');

  if (auth === 'certificate_p12') {
    var cf = document.getElementById('e-cert').files[0];
    if (cf) form.append('cert_file', cf);
    var pw = document.getElementById('e-certpw').value;
    if (pw) form.append('cert_password', pw);
  } else if (auth === 'certificate_pem') {
    var pf = document.getElementById('e-pemcert').files[0];
    if (pf) form.append('cert_file', pf);
    var kf = document.getElementById('e-pemkey').files[0];
    if (kf) form.append('key_file', kf);
  } else if (auth === 'knox_token') {
    var kt = document.getElementById('e-ktoken').value;
    if (kt) form.append('knox_token', kt);
  } else if (auth === 'knox_cookie') {
    var kc = document.getElementById('e-kcookie').value;
    if (kc) form.append('knox_cookie', kc);
  } else if (auth === 'knox_passcode') {
    var kp = document.getElementById('e-kpass').value;
    if (kp) form.append('knox_passcode', kp);
    form.append('knox_gateway_url', document.getElementById('e-kgw1').value);
  } else if (auth === 'basic') {
    form.append('knox_user', document.getElementById('e-user').value);
    var bp = document.getElementById('e-pass').value;
    if (bp) form.append('knox_password', bp);
    form.append('knox_gateway_url', document.getElementById('e-kgw2').value);
  }

  var r = await api('/api/edit', { method: 'POST', body: form });
  if (!r) { return; }

  if (r && r.error) { toast(T.msg_error + ': ' + r.error, true); return; }
  document.querySelector('.overlay').remove();
  toast(T.msg_saved + ': ' + newName);
  loadConns();
}

/* ═══ DELETE ═══ */
function confirmDelete(name) {
  var ov = document.createElement('div');
  ov.className = 'overlay';
  ov.innerHTML =
    '<div class="modal" style="width:360px;text-align:center">' +
      '<h3>' + T.confirm_delete + ' "' + escHtml(name) + '"?</h3>' +
      '<p style="color:#94a3b8;font-size:.82rem;margin-bottom:14px">' + T.confirm_delete_text + '</p>' +
      '<div style="display:flex;gap:6px;justify-content:center">' +
        '<button class="btn" onclick="this.closest(\'.overlay\').remove()">' + T.btn_cancel + '</button>' +
        '<button class="btn btn-ds" onclick="doDelete(\'' + escAttr(name) + '\')">' + T.btn_delete + '</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(ov);
  ov.addEventListener('click', function(e) { if (e.target === ov) ov.remove(); });
}

async function doDelete(name) {
  document.querySelector('.overlay').remove();
  var r = await api('/api/disconnect', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name}) });
  if (r && r.error) { toast(T.msg_error + ': ' + r.error, true); }
  else { toast(T.msg_disconnected + ': ' + name); }
  loadConns();
}

loadConns();
toggleAuth();
</script>
<div class="footer">
nifi-mcp-universal &mdash;
<a href="https://github.com/AlekseiSeleznev/nifi-mcp-universal">GitHub</a> &mdash;
<a href="https://github.com/AlekseiSeleznev/nifi-mcp-universal/blob/main/LICENSE">MIT License</a>
</div>
</body>
</html>"""


# ── Documentation page ──────────────────────────────────────────────
_DOC_STYLE = """body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px;max-width:900px;margin:0 auto;line-height:1.6;font-size:.88rem}
a{color:#38bdf8;text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.3rem;margin-bottom:4px}h2{font-size:1rem;margin-top:24px;margin-bottom:8px;color:#f8fafc;border-bottom:1px solid #334155;padding-bottom:4px}
h3{font-size:.88rem;margin-top:16px;margin-bottom:4px;color:#cbd5e1}
.sub{color:#64748b;font-size:.78rem}
code{background:#1e293b;padding:1px 5px;border-radius:3px;font-size:.82rem;color:#38bdf8}
pre{background:#1e293b;padding:12px;border-radius:6px;overflow-x:auto;font-size:.8rem;border:1px solid #334155;margin:8px 0}
pre code{background:none;padding:0;color:#e2e8f0}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:.82rem}
th{text-align:left;padding:6px 8px;border-bottom:1px solid #334155;color:#94a3b8;font-size:.72rem;text-transform:uppercase}
td{padding:6px 8px;border-bottom:1px solid rgba(51,65,85,.4)}
td code{font-size:.78rem}
.back{display:inline-block;margin-bottom:16px;font-size:.82rem}
ul{margin:4px 0 4px 20px}li{margin:2px 0}"""

_TOOLS_TABLE_RU = """<h3>Управление подключениями</h3>
<table><tr><th>Tool</th><th>Описание</th></tr>
<tr><td><code>connect_nifi</code></td><td>Подключиться к NiFi</td></tr>
<tr><td><code>disconnect_nifi</code></td><td>Отключиться от NiFi</td></tr>
<tr><td><code>switch_nifi</code></td><td>Переключить активное подключение</td></tr>
<tr><td><code>list_nifi_connections</code></td><td>Список подключений</td></tr>
<tr><td><code>get_server_status</code></td><td>Статус шлюза</td></tr>
<tr><td><code>test_nifi_connection</code></td><td>Тест подключения без сохранения</td></tr>
</table>

<h3>Обзор потоков (Read-only)</h3>
<table><tr><th>Tool</th><th>Описание</th></tr>
<tr><td><code>get_nifi_version</code></td><td>Версия NiFi</td></tr>
<tr><td><code>get_root_process_group</code></td><td>Корневая группа процессов</td></tr>
<tr><td><code>list_processors</code></td><td>Список процессоров</td></tr>
<tr><td><code>list_connections</code></td><td>Список соединений</td></tr>
<tr><td><code>get_bulletins</code></td><td>Системные уведомления</td></tr>
<tr><td><code>list_parameter_contexts</code></td><td>Контексты параметров</td></tr>
<tr><td><code>get_controller_services</code></td><td>Controller-сервисы</td></tr>
<tr><td><code>get_processor_types</code></td><td>Доступные типы процессоров</td></tr>
<tr><td><code>search_flow</code></td><td>Поиск компонентов</td></tr>
<tr><td><code>get_connection_details</code></td><td>Детали соединения</td></tr>
<tr><td><code>get_processor_details</code></td><td>Детали процессора</td></tr>
<tr><td><code>list_input_ports</code></td><td>Input-порты</td></tr>
<tr><td><code>list_output_ports</code></td><td>Output-порты</td></tr>
<tr><td><code>get_processor_state</code></td><td>Состояние процессора</td></tr>
<tr><td><code>check_connection_queue</code></td><td>Размер очереди</td></tr>
<tr><td><code>get_flow_summary</code></td><td>Сводка по группе</td></tr>
<tr><td><code>get_flow_health_status</code></td><td>Здоровье потока</td></tr>
<tr><td><code>get_controller_service_details</code></td><td>Детали сервиса</td></tr>
<tr><td><code>find_controller_services_by_type</code></td><td>Поиск сервисов по типу</td></tr>
<tr><td><code>get_parameter_context_details</code></td><td>Детали контекста параметров</td></tr>
</table>

<h3>Рекомендации и шаблоны</h3>
<table><tr><th>Tool</th><th>Описание</th></tr>
<tr><td><code>analyze_flow_build_request</code></td><td>Анализ запроса на построение потока</td></tr>
<tr><td><code>get_setup_instructions</code></td><td>Инструкции по настройке</td></tr>
<tr><td><code>check_configuration</code></td><td>Проверка конфигурации</td></tr>
<tr><td><code>get_best_practices_guide</code></td><td>Руководство по лучшим практикам</td></tr>
<tr><td><code>get_recommended_workflow</code></td><td>Рекомендуемый workflow</td></tr>
</table>

<h3>Запись (требуют readonly=false)</h3>
<table><tr><th>Tool</th><th>Описание</th></tr>
<tr><td><code>start_processor</code></td><td>Запуск процессора</td></tr>
<tr><td><code>stop_processor</code></td><td>Остановка процессора</td></tr>
<tr><td><code>create_processor</code></td><td>Создание процессора</td></tr>
<tr><td><code>update_processor_config</code></td><td>Обновление конфигурации</td></tr>
<tr><td><code>delete_processor</code></td><td>Удаление процессора</td></tr>
<tr><td><code>terminate_processor</code></td><td>Принудительная остановка</td></tr>
<tr><td><code>start_all_processors_in_group</code></td><td>Запуск всех в группе</td></tr>
<tr><td><code>stop_all_processors_in_group</code></td><td>Остановка всех в группе</td></tr>
<tr><td><code>create_connection</code></td><td>Создание соединения</td></tr>
<tr><td><code>delete_connection</code></td><td>Удаление соединения</td></tr>
<tr><td><code>empty_connection_queue</code></td><td>Очистка очереди</td></tr>
<tr><td><code>create_controller_service</code></td><td>Создание сервиса</td></tr>
<tr><td><code>update_controller_service_properties</code></td><td>Обновление свойств</td></tr>
<tr><td><code>enable_controller_service</code></td><td>Активация сервиса</td></tr>
<tr><td><code>disable_controller_service</code></td><td>Деактивация сервиса</td></tr>
<tr><td><code>delete_controller_service</code></td><td>Удаление сервиса</td></tr>
<tr><td><code>enable_all_controller_services_in_group</code></td><td>Активация всех сервисов</td></tr>
<tr><td><code>start_new_flow</code></td><td>Новый поток (best practices)</td></tr>
<tr><td><code>create_process_group</code></td><td>Создание группы</td></tr>
<tr><td><code>update_process_group_name</code></td><td>Переименование группы</td></tr>
<tr><td><code>delete_process_group</code></td><td>Удаление группы</td></tr>
<tr><td><code>create_input_port</code> / <code>create_output_port</code></td><td>Создание портов</td></tr>
<tr><td><code>update_input_port</code> / <code>update_output_port</code></td><td>Переименование портов</td></tr>
<tr><td><code>delete_input_port</code> / <code>delete_output_port</code></td><td>Удаление портов</td></tr>
<tr><td><code>start_input_port</code> / <code>start_output_port</code></td><td>Запуск портов</td></tr>
<tr><td><code>stop_input_port</code> / <code>stop_output_port</code></td><td>Остановка портов</td></tr>
<tr><td><code>create_parameter_context</code></td><td>Создание контекста</td></tr>
<tr><td><code>update_parameter_context</code></td><td>Обновление контекста</td></tr>
<tr><td><code>delete_parameter_context</code></td><td>Удаление контекста</td></tr>
<tr><td><code>apply_parameter_context_to_process_group</code></td><td>Привязка контекста</td></tr>
</table>"""

_TOOLS_TABLE_EN = """<h3>Connection Management</h3>
<table><tr><th>Tool</th><th>Description</th></tr>
<tr><td><code>connect_nifi</code></td><td>Connect to a NiFi instance</td></tr>
<tr><td><code>disconnect_nifi</code></td><td>Disconnect from a NiFi instance</td></tr>
<tr><td><code>switch_nifi</code></td><td>Switch the active connection</td></tr>
<tr><td><code>list_nifi_connections</code></td><td>List saved connections</td></tr>
<tr><td><code>get_server_status</code></td><td>Gateway status</td></tr>
<tr><td><code>test_nifi_connection</code></td><td>Test a connection without saving it</td></tr>
</table>

<h3>Flow Inspection (Read-only)</h3>
<table><tr><th>Tool</th><th>Description</th></tr>
<tr><td><code>get_nifi_version</code></td><td>NiFi version</td></tr>
<tr><td><code>get_root_process_group</code></td><td>Root process group</td></tr>
<tr><td><code>list_processors</code></td><td>List processors</td></tr>
<tr><td><code>list_connections</code></td><td>List connections</td></tr>
<tr><td><code>get_bulletins</code></td><td>System bulletins</td></tr>
<tr><td><code>list_parameter_contexts</code></td><td>Parameter contexts</td></tr>
<tr><td><code>get_controller_services</code></td><td>Controller services</td></tr>
<tr><td><code>get_processor_types</code></td><td>Available processor types</td></tr>
<tr><td><code>search_flow</code></td><td>Search components</td></tr>
<tr><td><code>get_connection_details</code></td><td>Connection details</td></tr>
<tr><td><code>get_processor_details</code></td><td>Processor details</td></tr>
<tr><td><code>list_input_ports</code></td><td>Input ports</td></tr>
<tr><td><code>list_output_ports</code></td><td>Output ports</td></tr>
<tr><td><code>get_processor_state</code></td><td>Processor state</td></tr>
<tr><td><code>check_connection_queue</code></td><td>Queue size</td></tr>
<tr><td><code>get_flow_summary</code></td><td>Process group summary</td></tr>
<tr><td><code>get_flow_health_status</code></td><td>Flow health status</td></tr>
<tr><td><code>get_controller_service_details</code></td><td>Controller service details</td></tr>
<tr><td><code>find_controller_services_by_type</code></td><td>Find services by type</td></tr>
<tr><td><code>get_parameter_context_details</code></td><td>Parameter context details</td></tr>
</table>

<h3>Guidance & Templates</h3>
<table><tr><th>Tool</th><th>Description</th></tr>
<tr><td><code>analyze_flow_build_request</code></td><td>Analyze a flow build request</td></tr>
<tr><td><code>get_setup_instructions</code></td><td>Setup instructions</td></tr>
<tr><td><code>check_configuration</code></td><td>Configuration check</td></tr>
<tr><td><code>get_best_practices_guide</code></td><td>Best practices guide</td></tr>
<tr><td><code>get_recommended_workflow</code></td><td>Recommended workflow</td></tr>
</table>

<h3>Write Operations (require readonly=false)</h3>
<table><tr><th>Tool</th><th>Description</th></tr>
<tr><td><code>start_processor</code></td><td>Start a processor</td></tr>
<tr><td><code>stop_processor</code></td><td>Stop a processor</td></tr>
<tr><td><code>create_processor</code></td><td>Create a processor</td></tr>
<tr><td><code>update_processor_config</code></td><td>Update processor configuration</td></tr>
<tr><td><code>delete_processor</code></td><td>Delete a processor</td></tr>
<tr><td><code>terminate_processor</code></td><td>Force-stop a processor</td></tr>
<tr><td><code>start_all_processors_in_group</code></td><td>Start all processors in a group</td></tr>
<tr><td><code>stop_all_processors_in_group</code></td><td>Stop all processors in a group</td></tr>
<tr><td><code>create_connection</code></td><td>Create a connection</td></tr>
<tr><td><code>delete_connection</code></td><td>Delete a connection</td></tr>
<tr><td><code>empty_connection_queue</code></td><td>Empty a connection queue</td></tr>
<tr><td><code>create_controller_service</code></td><td>Create a controller service</td></tr>
<tr><td><code>update_controller_service_properties</code></td><td>Update service properties</td></tr>
<tr><td><code>enable_controller_service</code></td><td>Enable a service</td></tr>
<tr><td><code>disable_controller_service</code></td><td>Disable a service</td></tr>
<tr><td><code>delete_controller_service</code></td><td>Delete a service</td></tr>
<tr><td><code>enable_all_controller_services_in_group</code></td><td>Enable all services in a group</td></tr>
<tr><td><code>start_new_flow</code></td><td>Start a new flow (best practices)</td></tr>
<tr><td><code>create_process_group</code></td><td>Create a process group</td></tr>
<tr><td><code>update_process_group_name</code></td><td>Rename a process group</td></tr>
<tr><td><code>delete_process_group</code></td><td>Delete a process group</td></tr>
<tr><td><code>create_input_port</code> / <code>create_output_port</code></td><td>Create ports</td></tr>
<tr><td><code>update_input_port</code> / <code>update_output_port</code></td><td>Rename ports</td></tr>
<tr><td><code>delete_input_port</code> / <code>delete_output_port</code></td><td>Delete ports</td></tr>
<tr><td><code>start_input_port</code> / <code>start_output_port</code></td><td>Start ports</td></tr>
<tr><td><code>stop_input_port</code> / <code>stop_output_port</code></td><td>Stop ports</td></tr>
<tr><td><code>create_parameter_context</code></td><td>Create a parameter context</td></tr>
<tr><td><code>update_parameter_context</code></td><td>Update a parameter context</td></tr>
<tr><td><code>delete_parameter_context</code></td><td>Delete a parameter context</td></tr>
<tr><td><code>apply_parameter_context_to_process_group</code></td><td>Apply a parameter context</td></tr>
</table>"""

DOCS_HTML = {
    "ru": """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>nifi-mcp-universal — Документация</title><style>""" + _DOC_STYLE + """</style></head><body>
<a class="back" href="/dashboard?lang=ru">&larr; Dashboard</a>
<h1>nifi-mcp-universal</h1>
<div class="sub">MCP-шлюз для Apache NiFi &middot; <a href="https://github.com/AlekseiSeleznev/nifi-mcp-universal">GitHub</a> &middot; MIT License</div>

<h2>Оглавление</h2>
<ul>
<li><a href="#s1">1. Обзор</a></li>
<li><a href="#s2">2. Быстрый старт</a></li>
<li><a href="#s3">3. Подключение MCP-клиента</a></li>
<li><a href="#s4">4. Codex (опционально)</a></li>
<li><a href="#s5">5. Dashboard</a></li>
<li><a href="#s6">6. MCP Tools</a></li>
<li><a href="#s7">7. Аутентификация</a></li>
<li><a href="#s8">8. Конфигурация</a></li>
<li><a href="#s9">9. API Endpoints</a></li>
<li><a href="#s10">10. Совместимость</a></li>
</ul>

<h2 id="s1">1. Обзор</h2>
<p>MCP-шлюз для Apache NiFi для любого клиента, поддерживающего <a href="https://modelcontextprotocol.io/">Model Context Protocol</a> по streamable HTTP.</p>
<ul>
<li>Multi-NiFi — подключение к нескольким NiFi инстансам одновременно</li>
<li>Per-session routing — каждая сессия работает со своим NiFi</li>
<li>66 MCP tools — управление, мониторинг, потоки, сервисы</li>
<li>Dashboard — веб-интерфейс с загрузкой сертификатов</li>
<li>Docker — запуск одной командой</li>
<li>NiFi 1.x и 2.x — автоматическое определение версии</li>
<li>Runbooks в репозитории: <code>CODEX.md</code>, <code>AGENTS.md</code></li>
<li>Автогенерируемый каталог инструментов: <code>docs/mcp-tool-catalog.md</code></li>
</ul>

<h2 id="s2">2. Быстрый старт</h2>
<pre><code>Linux / macOS:
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
./setup.sh

Windows:
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
.\\install.ps1</code></pre>
<p>Dashboard: <code>http://localhost:8085/dashboard</code></p>

<h2 id="s3">3. Подключение MCP-клиента</h2>
<p>Любому MCP-клиенту нужен streamable HTTP transport с MCP URL:</p>
<pre><code>http://localhost:8085/mcp</code></pre>
<p>Если включён <code>NIFI_MCP_API_KEY</code>, клиент должен отправлять Bearer token. Нейтральная manual-инструкция вынесена в <code>AGENTS.md</code>.</p>

<h2 id="s4">4. Codex (опционально)</h2>
<p>Если <code>codex</code> установлен, <code>setup.sh</code> и <code>install.ps1</code> попытаются зарегистрировать сервер автоматически. Ручная регистрация:</p>
<pre><code>codex mcp remove nifi-universal || true
codex mcp add nifi-universal --url http://localhost:8085/mcp
codex mcp get nifi-universal --json</code></pre>
<p>Если в <code>.env</code> задан <code>NIFI_MCP_API_KEY</code>, экспортируйте тот же ключ и используйте <code>--bearer-token-env-var NIFI_MCP_API_KEY</code>. Подробный сценарий описан в <code>CODEX.md</code>.</p>

<h2 id="s5">5. Dashboard</h2>
<p>Управление подключениями: <code>http://localhost:8085/dashboard</code></p>
<ul>
<li>Подключение и отключение NiFi инстансов</li>
<li>Загрузка сертификатов (P12, PEM)</li>
<li>Выбор метода аутентификации</li>
<li>Переключение активного NiFi</li>
<li>Read-only / Read-Write режим</li>
<li>Двуязычный интерфейс (RU/EN)</li>
<li>Bearer token не встраивается в HTML; вводится в браузере только при включённом <code>NIFI_MCP_API_KEY</code> и ответе 401</li>
</ul>

<h2 id="s6">6. MCP Tools</h2>
""" + _TOOLS_TABLE_RU + """

<h2 id="s7">7. Аутентификация</h2>
<ul>
<li><b>Certificate (P12)</b> — PKCS#12 файл с приватным ключом и сертификатом (mTLS)</li>
<li><b>Certificate (PEM)</b> — отдельные PEM/CRT и KEY файлы</li>
<li><b>Knox JWT Token</b> — JWT токен для CDP NiFi</li>
<li><b>Knox Cookie</b> — pre-authenticated cookie</li>
<li><b>Knox Passcode</b> — passcode + gateway URL</li>
<li><b>Basic Auth</b> — логин/пароль через Knox gateway</li>
<li><b>No Auth</b> — без аутентификации</li>
</ul>

<h2 id="s8">8. Конфигурация</h2>
<table><tr><th>Переменная</th><th>По умолчанию</th><th>Описание</th></tr>
<tr><td><code>NIFI_MCP_PORT</code></td><td>8085</td><td>Порт сервера</td></tr>
<tr><td><code>NIFI_MCP_LOG_LEVEL</code></td><td>INFO</td><td>Уровень логирования</td></tr>
<tr><td><code>NIFI_MCP_API_KEY</code></td><td>—</td><td>Bearer token для MCP и dashboard API endpoints</td></tr>
<tr><td><code>NIFI_MCP_NIFI_API_BASE</code></td><td>—</td><td>URL NiFi для авто-подключения</td></tr>
<tr><td><code>NIFI_MCP_NIFI_READONLY</code></td><td>true</td><td>Read-only по умолчанию</td></tr>
<tr><td><code>NIFI_MCP_HTTP_TIMEOUT</code></td><td>30</td><td>Таймаут HTTP (сек)</td></tr>
<tr><td><code>NIFI_MCP_SESSION_TIMEOUT</code></td><td>28800</td><td>Idle timeout сессий (сек)</td></tr>
<tr><td><code>NIFI_MCP_ENABLE_SIMPLE_TOKEN_ENDPOINT</code></td><td>false</td><td>Режим совместимости <code>/oauth/token</code></td></tr>
<tr><td><code>NIFI_MCP_PERSIST_SECRETS_IN_STATE</code></td><td>false</td><td>Сохранять секреты в state-файле</td></tr>
</table>

<h2 id="s9">9. API Endpoints</h2>
<table><tr><th>Endpoint</th><th>Метод</th><th>Описание</th></tr>
<tr><td><code>/mcp</code></td><td>POST</td><td>MCP Streamable HTTP transport</td></tr>
<tr><td><code>/health</code></td><td>GET</td><td>Health check</td></tr>
<tr><td><code>/dashboard</code></td><td>GET</td><td>Веб-интерфейс</td></tr>
<tr><td><code>/dashboard/docs</code></td><td>GET</td><td>Документация</td></tr>
<tr><td><code>/api/status</code></td><td>GET</td><td>Статус gateway</td></tr>
<tr><td><code>/api/connections</code></td><td>GET</td><td>Список подключений</td></tr>
<tr><td><code>/api/connect</code></td><td>POST</td><td>Подключить NiFi</td></tr>
<tr><td><code>/api/disconnect</code></td><td>POST</td><td>Отключить NiFi</td></tr>
<tr><td><code>/api/edit</code></td><td>POST</td><td>Редактировать подключение</td></tr>
<tr><td><code>/api/switch</code></td><td>POST</td><td>Переключить активное</td></tr>
<tr><td><code>/api/test</code></td><td>POST</td><td>Тест подключения</td></tr>
<tr><td><code>/.well-known/oauth-protected-resource</code></td><td>GET</td><td>RFC 9728 metadata</td></tr>
<tr><td><code>/.well-known/oauth-authorization-server</code></td><td>GET</td><td>RFC 8414 metadata</td></tr>
<tr><td><code>/oauth/token</code></td><td>POST</td><td>Compatibility endpoint (по умолчанию выключен)</td></tr>
</table>

<h2 id="s10">10. Совместимость</h2>
<ul>
<li>Apache NiFi 1.x, 2.x</li>
<li>Python 3.12+</li>
<li>Docker / Docker Compose v2</li>
<li>Linux, Windows</li>
</ul>
</body></html>""",

    "en": """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>nifi-mcp-universal — Documentation</title><style>""" + _DOC_STYLE + """</style></head><body>
<a class="back" href="/dashboard?lang=en">&larr; Dashboard</a>
<h1>nifi-mcp-universal</h1>
<div class="sub">MCP gateway for Apache NiFi &middot; <a href="https://github.com/AlekseiSeleznev/nifi-mcp-universal">GitHub</a> &middot; MIT License</div>

<h2>Contents</h2>
<ul>
<li><a href="#e1">1. Overview</a></li>
<li><a href="#e2">2. Quick Start</a></li>
<li><a href="#e3">3. MCP Client Setup</a></li>
<li><a href="#e4">4. Codex (Optional)</a></li>
<li><a href="#e5">5. Dashboard</a></li>
<li><a href="#e6">6. MCP Tools</a></li>
<li><a href="#e7">7. Authentication</a></li>
<li><a href="#e8">8. Configuration</a></li>
<li><a href="#e9">9. API Endpoints</a></li>
<li><a href="#e10">10. Compatibility</a></li>
</ul>

<h2 id="e1">1. Overview</h2>
<p>MCP gateway for Apache NiFi for any client that supports <a href="https://modelcontextprotocol.io/">Model Context Protocol</a> over streamable HTTP.</p>
<ul>
<li>Multi-NiFi — connect to multiple NiFi instances simultaneously</li>
<li>Per-session routing — each session works with its own NiFi</li>
<li>66 MCP tools — management, monitoring, flows, services</li>
<li>Dashboard — web UI with certificate upload</li>
<li>Docker — single command deployment</li>
<li>NiFi 1.x and 2.x — automatic version detection</li>
<li>Runbooks in the repo: <code>CODEX.md</code>, <code>AGENTS.md</code></li>
<li>Autogenerated tool catalog: <code>docs/mcp-tool-catalog.md</code></li>
</ul>

<h2 id="e2">2. Quick Start</h2>
<pre><code>Linux / macOS:
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
./setup.sh

Windows:
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
.\\install.ps1</code></pre>
<p>Dashboard: <code>http://localhost:8085/dashboard</code></p>

<h2 id="e3">3. MCP Client Setup</h2>
<p>Any MCP client needs a streamable HTTP transport with this MCP URL:</p>
<pre><code>http://localhost:8085/mcp</code></pre>
<p>If <code>NIFI_MCP_API_KEY</code> is enabled, the client must send a Bearer token. The generic manual onboarding guide lives in <code>AGENTS.md</code>.</p>

<h2 id="e4">4. Codex (Optional)</h2>
<p>If <code>codex</code> is installed, <code>setup.sh</code> and <code>install.ps1</code> try to register the server automatically. Manual registration:</p>
<pre><code>codex mcp remove nifi-universal || true
codex mcp add nifi-universal --url http://localhost:8085/mcp
codex mcp get nifi-universal --json</code></pre>
<p>If <code>NIFI_MCP_API_KEY</code> is configured in <code>.env</code>, export the same value and use <code>--bearer-token-env-var NIFI_MCP_API_KEY</code>. See <code>CODEX.md</code> for the exact workflow.</p>

<h2 id="e5">5. Dashboard</h2>
<p>Connection management: <code>http://localhost:8085/dashboard</code></p>
<ul>
<li>Connect and disconnect NiFi instances</li>
<li>Upload certificates (P12, PEM)</li>
<li>Select authentication method</li>
<li>Switch active NiFi</li>
<li>Read-only / Read-Write mode</li>
<li>Bilingual UI (RU/EN)</li>
<li>Bearer token is not embedded in HTML; prompted in browser only when <code>NIFI_MCP_API_KEY</code> is enabled and a 401 response is returned</li>
</ul>

<h2 id="e6">6. MCP Tools</h2>
""" + _TOOLS_TABLE_EN + """

<h2 id="e7">7. Authentication</h2>
<ul>
<li><b>Certificate (P12)</b> — PKCS#12 bundle with private key and certificate (mTLS)</li>
<li><b>Certificate (PEM)</b> — separate PEM/CRT and KEY files</li>
<li><b>Knox JWT Token</b> — JWT token for CDP NiFi</li>
<li><b>Knox Cookie</b> — pre-authenticated cookie</li>
<li><b>Knox Passcode</b> — passcode + gateway URL</li>
<li><b>Basic Auth</b> — username/password via Knox gateway</li>
<li><b>No Auth</b> — no authentication</li>
</ul>

<h2 id="e8">8. Configuration</h2>
<table><tr><th>Variable</th><th>Default</th><th>Description</th></tr>
<tr><td><code>NIFI_MCP_PORT</code></td><td>8085</td><td>Server port</td></tr>
<tr><td><code>NIFI_MCP_LOG_LEVEL</code></td><td>INFO</td><td>Log level</td></tr>
<tr><td><code>NIFI_MCP_API_KEY</code></td><td>—</td><td>Bearer token for MCP and dashboard API endpoints</td></tr>
<tr><td><code>NIFI_MCP_NIFI_API_BASE</code></td><td>—</td><td>NiFi URL for auto-connect</td></tr>
<tr><td><code>NIFI_MCP_NIFI_READONLY</code></td><td>true</td><td>Default read-only mode</td></tr>
<tr><td><code>NIFI_MCP_HTTP_TIMEOUT</code></td><td>30</td><td>HTTP timeout (sec)</td></tr>
<tr><td><code>NIFI_MCP_SESSION_TIMEOUT</code></td><td>28800</td><td>Session idle timeout (sec)</td></tr>
<tr><td><code>NIFI_MCP_ENABLE_SIMPLE_TOKEN_ENDPOINT</code></td><td>false</td><td>Compatibility <code>/oauth/token</code> toggle</td></tr>
<tr><td><code>NIFI_MCP_PERSIST_SECRETS_IN_STATE</code></td><td>false</td><td>Persist secrets in the state file</td></tr>
</table>

<h2 id="e9">9. API Endpoints</h2>
<table><tr><th>Endpoint</th><th>Method</th><th>Description</th></tr>
<tr><td><code>/mcp</code></td><td>POST</td><td>MCP Streamable HTTP transport</td></tr>
<tr><td><code>/health</code></td><td>GET</td><td>Health check</td></tr>
<tr><td><code>/dashboard</code></td><td>GET</td><td>Web UI</td></tr>
<tr><td><code>/dashboard/docs</code></td><td>GET</td><td>Documentation</td></tr>
<tr><td><code>/api/status</code></td><td>GET</td><td>Gateway status</td></tr>
<tr><td><code>/api/connections</code></td><td>GET</td><td>List connections</td></tr>
<tr><td><code>/api/connect</code></td><td>POST</td><td>Connect NiFi</td></tr>
<tr><td><code>/api/disconnect</code></td><td>POST</td><td>Disconnect NiFi</td></tr>
<tr><td><code>/api/edit</code></td><td>POST</td><td>Edit connection</td></tr>
<tr><td><code>/api/switch</code></td><td>POST</td><td>Switch active</td></tr>
<tr><td><code>/api/test</code></td><td>POST</td><td>Test connection</td></tr>
<tr><td><code>/.well-known/oauth-protected-resource</code></td><td>GET</td><td>RFC 9728 metadata</td></tr>
<tr><td><code>/.well-known/oauth-authorization-server</code></td><td>GET</td><td>RFC 8414 metadata</td></tr>
<tr><td><code>/oauth/token</code></td><td>POST</td><td>Compatibility endpoint (disabled by default)</td></tr>
</table>

<h2 id="e10">10. Compatibility</h2>
<ul>
<li>Apache NiFi 1.x, 2.x</li>
<li>Python 3.12+</li>
<li>Docker / Docker Compose v2</li>
<li>Linux, Windows</li>
</ul>
</body></html>""",
}


def render_docs(lang: str = "ru") -> str:
    return DOCS_HTML.get(lang, DOCS_HTML["ru"])
