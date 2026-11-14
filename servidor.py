"""
Jane Cabeleireira Hair — Sistema de Agendamentos (completo)
============================================================
Banco: PostgreSQL (se houver DATABASE_URL) OU SQLite (local, padrão).
WhatsApp: Twilio / Meta / mock (auto-detectado).
COMO EXECUTAR LOCAL: dois cliques em server.py → http://localhost:5000
PARA PUBLICAR (Replit/Render): crie um PostgreSQL gratuito (Neon/Supabase/Render),
cole a string de conexão na variável de ambiente DATABASE_URL.
"""

import os
import sys
import re
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")
IS_PG = bool(DATABASE_URL)

# ---- Auto-instala dependências na primeira execução ----
_NEED_INSTALL = []
try:
    import flask  # noqa: F401
except ImportError:
    _NEED_INSTALL.append("flask")
if IS_PG:
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        _NEED_INSTALL.append("psycopg2-binary")
if _NEED_INSTALL:
    import subprocess
    print(f"[Primeira execução] Instalando: {', '.join(_NEED_INSTALL)}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + _NEED_INSTALL)
        print("[OK] Dependências instaladas.")
    except Exception as e:
        print(f"[ERRO] Falha ao instalar: {e}")
        sys.exit(1)

from flask import Flask, request, jsonify, g

# ============================================================
#  CONFIG
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "agendamentos.db")
NOME_SALAO = "Jane Cabeleireira Hair"
SERVICOS = {}  # serviço é digitado livremente no formulário
PROFISSIONAIS = ["Jane"]

# ---- WhatsApp (Twilio configurado; deixe vazio para mock) ----
WHATSAPP_TOKEN         = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
TWILIO_SID             = os.environ.get("TWILIO_SID", "AC6d73699454ec455af37676d5abb1a698")
TWILIO_TOKEN           = os.environ.get("TWILIO_TOKEN", "561103dbc25509302114468466645a02")
TWILIO_FROM            = os.environ.get("TWILIO_FROM", "+17372508034")
WHATSAPP_API_VERSION   = os.environ.get("WHATSAPP_API_VERSION", "v21.0")
WHATSAPP_TIMEOUT       = int(os.environ.get("WHATSAPP_TIMEOUT", "15"))

if TWILIO_SID and TWILIO_TOKEN:
    _PROVEDOR_PADRAO = "twilio"
elif WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID:
    _PROVEDOR_PADRAO = "meta"
else:
    _PROVEDOR_PADRAO = "mock"
WHATSAPP_PROVIDER = os.environ.get("WHATSAPP_PROVIDER", _PROVEDOR_PADRAO).lower()

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

# ============================================================
#  BANCO DE DADOS — camada única (PostgreSQL OU SQLite)
# ============================================================
SCHEMA_COLS = """
    nome_cliente    TEXT NOT NULL,
    telefone        TEXT NOT NULL,
    data_hora       TEXT NOT NULL,
    servico         TEXT DEFAULT '',
    profissional    TEXT DEFAULT '',
    valor           REAL DEFAULT 0,
    status          TEXT DEFAULT 'agendado',
    whatsapp_enviado INTEGER DEFAULT 0,
    whatsapp_erro   TEXT DEFAULT ''
"""

if IS_PG:
    import psycopg2
    import psycopg2.extras

    class _DB:
        def __init__(self):
            self.conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            self.conn.autocommit = False
        def execute(self, sql, params=()):
            cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            return cur
        def commit(self): self.conn.commit()
        def close(self):
            try: self.conn.close()
            except Exception: pass

    def init_db():
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"""CREATE TABLE IF NOT EXISTS agendamentos (
            id SERIAL PRIMARY KEY, {SCHEMA_COLS},
            criado_em TIMESTAMP DEFAULT NOW()
        )""")
        for col, tipo in [("profissional", "TEXT DEFAULT ''"), ("valor", "REAL DEFAULT 0")]:
            try:
                cur.execute(f"ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS {col} {tipo}")
            except Exception:
                pass
        cur.close(); conn.close()
        print("[BD] Conectado ao PostgreSQL (persistente).")
else:
    import sqlite3

    class _DB:
        def __init__(self):
            self.conn = sqlite3.connect(DB_PATH)
            self.conn.row_factory = sqlite3.Row
        def execute(self, sql, params=()):
            cur = self.conn.cursor()
            cur.execute(sql.replace("%s", "?"), params)
            return cur
        def commit(self): self.conn.commit()
        def close(self):
            try: self.conn.close()
            except Exception: pass

    def init_db():
        conn = sqlite3.connect(DB_PATH)
        conn.execute(f"""CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, {SCHEMA_COLS},
            criado_em TEXT DEFAULT (datetime('now','localtime'))
        )""")
        for col, tipo in [("profissional", "TEXT DEFAULT ''"), ("valor", "REAL DEFAULT 0")]:
            try:
                conn.execute(f"ALTER TABLE agendamentos ADD COLUMN {col} {tipo}")
            except sqlite3.OperationalError:
                pass
        conn.commit(); conn.close()
        print(f"[BD] SQLite (local) em: {DB_PATH}")


def get_db():
    if "db" not in g:
        g.db = _DB()
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def rows_as_dicts(cur):
    return [dict(r) for r in cur.fetchall()]

# ============================================================
#  WHATSAPP
# ============================================================
def normalizar_telefone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("0"):
        digits = digits[1:]
    if len(digits) in (10, 11):
        digits = "55" + digits
    return digits

def formatar_data_hora(iso):
    try:
        dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M")
        return dt.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        return iso.replace("T", " ")

def montar_mensagem(nome, data_hora, servico):
    extra = ""
    if servico:
        extra += f"\nServiço: {servico}"
    return (
        f"Olá {nome}! Seu agendamento na {NOME_SALAO} está confirmado.\n"
        f"Data e hora: {formatar_data_hora(data_hora)}"
        f"{extra}\n"
        f"Responda esta mensagem para remarcar ou cancelar."
    )

def enviar_whatsapp_meta(to, texto):
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp", "to": to, "type": "text",
        "text": {"body": texto},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=WHATSAPP_TIMEOUT) as resp:
            print(f"[WhatsApp/meta] {resp.status}: {resp.read().decode()[:200]}")
            return True, ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return False, str(e)[:300]

def enviar_whatsapp_twilio(to, texto):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    dados = urllib.parse.urlencode({
        "To": f"whatsapp:+{to}",
        "From": f"whatsapp:{TWILIO_FROM}",
        "Body": texto,
    }).encode("utf-8")
    credencial = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
    req = urllib.request.Request(
        url, data=dados, method="POST",
        headers={"Authorization": f"Basic {credencial}",
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=WHATSAPP_TIMEOUT) as resp:
            print(f"[WhatsApp/twilio] {resp.status}: {resp.read().decode()[:200]}")
            return True, ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return False, str(e)[:300]

def disparar_whatsapp(to, texto):
    if WHATSAPP_PROVIDER == "mock":
        print("=" * 60)
        print("[WhatsApp/MOCK] Mensagem que seria enviada:")
        print(f"  Para: +{to}")
        print(texto)
        print("=" * 60)
        return True, "mock (não enviado de verdade)"
    if WHATSAPP_PROVIDER == "meta":
        if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
            return False, "Token/Phone Number ID ausentes"
        return enviar_whatsapp_meta(to, texto)
    if WHATSAPP_PROVIDER == "twilio":
        if not TWILIO_SID or not TWILIO_TOKEN:
            return False, "Twilio SID/Token ausentes"
        return enviar_whatsapp_twilio(to, texto)
    return False, f"Provider desconhecido: {WHATSAPP_PROVIDER}"

# ============================================================
#  ROTAS
# ============================================================
@app.route("/")
def pagina():
    return app.send_static_file("cadastro-atendimento.html")

@app.route("/api/config")
def api_config():
    return jsonify({"servicos": SERVICOS, "profissionais": PROFISSIONAIS, "salao": NOME_SALAO})

def validar(dados):
    erros = []
    nome = (dados.get("nome_cliente") or "").strip()
    data_hora = (dados.get("data_hora") or "").strip()
    if not nome:
        erros.append("Informe o nome do(a) cliente.")
    if not data_hora or "T" not in data_hora:
        erros.append("Informe a data e hora do atendimento.")
    try:
        valor = float(dados.get("valor") or 0)
    except (ValueError, TypeError):
        valor = 0.0
    return erros, {
        "nome_cliente": nome, "telefone": "Não informado", "data_hora": data_hora,
        "servico": (dados.get("servico") or "").strip(),
        "profissional": "",
        "valor": valor,
    }

@app.route("/api/agendamentos", methods=["GET", "POST"])
def agendamentos():
    db = get_db()
    if request.method == "POST":
        dados = request.get_json(silent=True) or request.form
        erros, vals = validar(dados)
        if erros:
            return jsonify({"ok": False, "erros": erros}), 400
        cur = db.execute(
            """INSERT INTO agendamentos (nome_cliente, telefone, data_hora, servico, profissional, valor)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (vals["nome_cliente"], vals["telefone"], vals["data_hora"],
             vals["servico"], vals["profissional"], vals["valor"]),
        )
        aid = dict(cur.fetchone())["id"]
        db.commit()
        texto = montar_mensagem(vals["nome_cliente"], vals["data_hora"], vals["servico"])
        enviado, erro = disparar_whatsapp(vals["telefone"], texto)
        db.execute("UPDATE agendamentos SET whatsapp_enviado=%s, whatsapp_erro=%s WHERE id=%s",
                   (1 if enviado else 0, erro, aid))
        db.commit()
        return jsonify({"ok": True, "id": aid, "whatsapp_enviado": enviado, "whatsapp_erro": erro,
                        "mensagem": f"Agendamento #{aid} cadastrado."})
    cur = db.execute("SELECT * FROM agendamentos ORDER BY data_hora DESC")
    return jsonify(rows_as_dicts(cur))

@app.route("/api/agendamentos/<int:aid>", methods=["GET", "PUT", "DELETE"])
def agendamento_id(aid):
    db = get_db()
    cur = db.execute("SELECT * FROM agendamentos WHERE id=%s", (aid,))
    row = cur.fetchone()
    if not row:
        return jsonify({"ok": False, "erro": "Agendamento não encontrado."}), 404
    row = dict(row)
    if request.method == "GET":
        return jsonify(row)
    if request.method == "DELETE":
        db.execute("DELETE FROM agendamentos WHERE id=%s", (aid,))
        db.commit()
        return jsonify({"ok": True, "mensagem": "Agendamento excluído."})
    dados = request.get_json(silent=True) or request.form
    erros, vals = validar(dados)
    if erros:
        return jsonify({"ok": False, "erros": erros}), 400
    db.execute(
        """UPDATE agendamentos SET nome_cliente=%s, telefone=%s, data_hora=%s,
           servico=%s, profissional=%s, valor=%s WHERE id=%s""",
        (vals["nome_cliente"], vals["telefone"], vals["data_hora"],
         vals["servico"], vals["profissional"], vals["valor"], aid),
    )
    db.commit()
    return jsonify({"ok": True, "mensagem": "Agendamento atualizado."})

@app.route("/api/agendamentos/<int:aid>/status", methods=["POST"])
def mudar_status(aid):
    db = get_db()
    cur = db.execute("SELECT id FROM agendamentos WHERE id=%s", (aid,))
    if not cur.fetchone():
        return jsonify({"ok": False, "erro": "Agendamento não encontrado."}), 404
    dados = request.get_json(silent=True) or request.form
    status = (dados.get("status") or "").strip()
    if status not in ("agendado", "cancelado", "concluido"):
        return jsonify({"ok": False, "erro": "Status inválido."}), 400
    db.execute("UPDATE agendamentos SET status=%s WHERE id=%s", (status, aid))
    db.commit()
    return jsonify({"ok": True, "mensagem": f"Status alterado para: {status}."})

@app.route("/api/financeiro")
def financeiro():
    db = get_db()
    mes = (request.args.get("mes") or "").strip()
    if mes and re.match(r"^\d{4}-\d{2}$", mes):
        filtro = "WHERE data_hora LIKE %s"
        params = (mes + "%",)
    else:
        filtro = ""
        params = ()
    cur = db.execute(f"SELECT * FROM agendamentos {filtro} ORDER BY data_hora DESC", params)
    rows = rows_as_dicts(cur)
    total = recebido = a_receber = cancelado = 0.0
    for r in rows:
        v = float(r.get("valor") or 0)
        total += v
        if r.get("status") == "concluido":
            recebido += v
        elif r.get("status") == "agendado":
            a_receber += v
        elif r.get("status") == "cancelado":
            cancelado += v
    return jsonify({
        "mes": mes or "todos",
        "total_geral": round(total, 2),
        "recebido": round(recebido, 2),
        "a_receber": round(a_receber, 2),
        "cancelado": round(cancelado, 2),
        "por_profissional": [],
        "quantidade": len(rows),
        "lista": rows,
    })

# ============================================================
#  STARTUP
# ============================================================
if __name__ == "__main__":
    try:
        init_db()
        print(f"[WhatsApp] provider = {WHATSAPP_PROVIDER}")
        porta = int(os.environ.get("PORT", "5000"))
        print(f"[Servidor] Rodando em http://localhost:{porta}  (Ctrl+C para parar)")
        try:
            import webbrowser
            webbrowser.open(f"http://localhost:{porta}")
        except Exception:
            pass
        app.run(host="0.0.0.0", port=porta, debug=False)
    except KeyboardInterrupt:
        print("\nServidor parado.")
    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
