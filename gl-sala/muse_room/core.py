"""Transactional local domain. All identities and permissions come from the DB."""
import hashlib
import json
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager


class Problem(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value, field, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise Problem(400, "invalid_input", "Campo inválido: " + field)
    return value.strip()


def fields(data, required, optional=()):
    if not isinstance(data, dict) or set(data) - set(required) - set(optional) or set(required) - set(data):
        raise Problem(400, "invalid_fields", "Faltan campos o hay campos no admitidos.")


SCHEMA = """
CREATE TABLE IF NOT EXISTS identities (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('human','agent')),
 token_hash TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1,
 admin INTEGER NOT NULL DEFAULT 0, agent_write INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, name TEXT NOT NULL, site TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members (
 room_id TEXT NOT NULL REFERENCES rooms(id), actor_id TEXT NOT NULL REFERENCES identities(id),
 role TEXT NOT NULL CHECK(role IN ('member','approver')), PRIMARY KEY(room_id,actor_id));
CREATE TABLE IF NOT EXISTS messages (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id),
 actor_id TEXT NOT NULL REFERENCES identities(id), text TEXT NOT NULL, targets TEXT NOT NULL,
 reply_to TEXT REFERENCES messages(id), created_at REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_reply ON messages(actor_id, reply_to) WHERE reply_to IS NOT NULL;
CREATE TABLE IF NOT EXISTS requests (
 id TEXT PRIMARY KEY, room_id TEXT NOT NULL REFERENCES rooms(id), actor_id TEXT NOT NULL REFERENCES identities(id),
 payload TEXT NOT NULL, payload_digest TEXT NOT NULL, status TEXT NOT NULL,
 reviewer TEXT REFERENCES identities(id), created_at REAL NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, room_id TEXT NOT NULL REFERENCES rooms(id), actor_id TEXT NOT NULL REFERENCES identities(id),
 goal TEXT NOT NULL, lead_id TEXT NOT NULL REFERENCES identities(id), contributors TEXT NOT NULL,
 status TEXT NOT NULL, synthesis TEXT, created_at REAL NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS contributions (
 task_id TEXT NOT NULL REFERENCES tasks(id), actor_id TEXT NOT NULL REFERENCES identities(id),
 text TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(task_id,actor_id));
CREATE TABLE IF NOT EXISTS receipts (
 actor_id TEXT NOT NULL, route TEXT NOT NULL, key TEXT NOT NULL, payload_digest TEXT NOT NULL,
 response TEXT NOT NULL, PRIMARY KEY(actor_id,route,key));
CREATE TABLE IF NOT EXISTS audit (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, event TEXT NOT NULL,
 prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'append only'); END;
"""


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def audit(self, db, actor, action, target, room=None, details=None):
        previous = db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        previous = previous[0] if previous else "0" * 64
        event = canonical(dict(actor=actor, action=action, target=target, room=room, details=details or {}, at=time.time()))
        hashed = hashlib.sha256((previous + event).encode()).hexdigest()
        db.execute("INSERT INTO audit(room_id,event,prev_hash,hash) VALUES(?,?,?,?)", (room, event, previous, hashed))

    def create_identity(self, name, kind="human", admin=False, agent_write=False):
        name = text(name, "name", 80)
        if kind not in ("human", "agent") or (kind == "agent" and admin) or (kind == "human" and agent_write):
            raise Problem(400, "invalid_identity", "Tipo o permisos de identidad inválidos.")
        actor, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
        with self.transaction() as db:
            db.execute("INSERT INTO identities(id,name,kind,token_hash,admin,agent_write) VALUES(?,?,?,?,?,?)",
                       (actor, name, kind, hashlib.sha256(token.encode()).hexdigest(), int(admin), int(agent_write)))
            self.audit(db, "local-operator", "identity.created", actor, details={"kind": kind})
        return actor, token

    def revoke(self, actor):
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM identities WHERE id=?", (actor,)).fetchone():
                raise Problem(404, "not_found", "Identidad inexistente.")
            db.execute("UPDATE identities SET active=0 WHERE id=?", (actor,))
            self.audit(db, "local-operator", "identity.revoked", actor)

    def authenticate(self, db, token):
        if not isinstance(token, str) or len(token) > 256:
            raise Problem(401, "unauthenticated", "Clave inválida o revocada.")
        actor = db.execute("SELECT id,name,kind,admin,agent_write FROM identities WHERE token_hash=? AND active=1",
                           (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not actor:
            raise Problem(401, "unauthenticated", "Clave inválida o revocada.")
        return dict(actor)

    def member(self, db, actor, room):
        row = db.execute("SELECT m.role,r.site,r.name FROM members m JOIN rooms r ON r.id=m.room_id WHERE m.room_id=? AND m.actor_id=?",
                         (room, actor["id"])).fetchone()
        if not row:
            raise Problem(403, "room_forbidden", "No tenés acceso a esta sala.")
        return dict(row)

    def participants(self, db, room):
        return [dict(r) for r in db.execute("SELECT i.id,i.name,i.kind,i.active,i.agent_write,m.role FROM identities i JOIN members m ON m.actor_id=i.id WHERE m.room_id=? ORDER BY i.kind DESC,i.name", (room,))]

    def agent_ids(self, db, room, ids):
        if not isinstance(ids, list) or len(ids) > 4 or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
            raise Problem(400, "invalid_agents", "Elegí hasta cuatro agentes distintos.")
        allowed = {p["id"] for p in self.participants(db, room) if p["kind"] == "agent" and p["active"]}
        if not set(ids) <= allowed:
            raise Problem(400, "invalid_agents", "Agente fuera de la sala o revocado.")

    def agent_writer(self, actor):
        if actor["kind"] != "agent" or not actor["agent_write"]:
            raise Problem(403, "agent_read_only", "Se requiere una cuenta de agente con escritura habilitada localmente.")

    def mutate(self, token, route, key, data):
        if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{8,128}", key):
            raise Problem(400, "idempotency_required", "Se requiere Idempotency-Key de 8 a 128 caracteres.")
        body_hash = digest(data)
        with self.transaction() as db:
            actor = self.authenticate(db, token)
            # Authorization precedes receipt lookup, including membership after revocation.
            parts = route.strip("/").split("/")
            if len(parts) >= 3 and parts[:2] == ["api", "rooms"]:
                self.member(db, actor, parts[2])
            receipt = db.execute("SELECT * FROM receipts WHERE actor_id=? AND route=? AND key=?", (actor["id"], route, key)).fetchone()
            if receipt:
                if receipt["payload_digest"] != body_hash:
                    raise Problem(409, "idempotency_conflict", "La clave ya se usó con otros datos.")
                return json.loads(receipt["response"])
            result = self._write(db, actor, parts, data)
            db.execute("INSERT INTO receipts VALUES(?,?,?,?,?)", (actor["id"], route, key, body_hash, canonical(result)))
            return result

    def _write(self, db, actor, parts, data):
        if parts == ["api", "rooms"]:
            fields(data, ("name", "site", "members"))
            if actor["kind"] != "human" or not actor["admin"]:
                raise Problem(403, "admin_required", "Solo la persona administradora puede crear salas.")
            name, site = text(data["name"], "name", 80), text(data["site"], "site", 80)
            members = data["members"]
            if not isinstance(members, list) or len(members) > 30:
                raise Problem(400, "invalid_members", "Lista de integrantes inválida.")
            chosen = {actor["id"]: "approver"}
            for entry in members:
                fields(entry, ("id", "role"))
                identity = db.execute("SELECT * FROM identities WHERE id=? AND active=1", (text(entry["id"], "id", 40),)).fetchone()
                if not identity or entry["role"] not in ("member", "approver") or (identity["kind"] == "agent" and entry["role"] == "approver"):
                    raise Problem(400, "invalid_members", "Integrante o rol no permitido.")
                if entry["id"] in chosen:
                    raise Problem(400, "duplicate_member", "No repitas integrantes ni al creador de la sala.")
                chosen[entry["id"]] = entry["role"]
            room = uuid.uuid4().hex
            db.execute("INSERT INTO rooms VALUES(?,?,?)", (room, name, site))
            db.executemany("INSERT INTO members VALUES(?,?,?)", [(room, a, role) for a, role in chosen.items()])
            self.audit(db, actor["id"], "room.created", room, room, {"members": chosen, "site": site})
            return {"id": room}
        if len(parts) < 4 or parts[:2] != ["api", "rooms"]:
            raise Problem(404, "not_found", "Operación inexistente.")
        room = parts[2]
        membership = self.member(db, actor, room)
        action = parts[3:]
        now = time.time()
        if action == ["messages"]:
            fields(data, ("text",), ("targets", "reply_to"))
            content = text(data["text"], "text", 4000)
            targets, reply = data.get("targets", []), data.get("reply_to")
            self.agent_ids(db, room, targets)
            if actor["kind"] == "agent":
                self.agent_writer(actor)
                parent = db.execute("SELECT m.*,i.kind FROM messages m JOIN identities i ON i.id=m.actor_id WHERE m.id=? AND m.room_id=? AND i.active=1", (text(reply, "reply_to", 40), room)).fetchone()
                if targets or not parent or parent["kind"] != "human" or actor["id"] not in json.loads(parent["targets"]):
                    raise Problem(403, "not_addressed", "Solo podés responder a una intervención humana dirigida a esta cuenta.")
                if now - parent["created_at"] > 86400:
                    raise Problem(409, "expired", "La intervención ya venció.")
                if db.execute("SELECT 1 FROM messages WHERE actor_id=? AND reply_to=?", (actor["id"], reply)).fetchone():
                    raise Problem(409, "already_replied", "Esta cuenta ya respondió a esa intervención.")
            elif reply is not None:
                raise Problem(400, "invalid_reply", "Las respuestas enlazadas están reservadas al conector de agentes.")
            msg = uuid.uuid4().hex
            db.execute("INSERT INTO messages(id,room_id,actor_id,text,targets,reply_to,created_at) VALUES(?,?,?,?,?,?,?)", (msg, room, actor["id"], content, canonical(targets), reply, now))
            self.audit(db, actor["id"], "message.created", msg, room, {"content_hash": digest(content)})
            return {"id": msg}
        if action == ["requests"]:
            fields(data, ("sku", "quantity", "note"))
            if actor["kind"] != "human":
                raise Problem(403, "human_required", "Las solicitudes de stock requieren identidad humana.")
            if data["sku"] not in ("DEMO-001", "DEMO-002") or type(data["quantity"]) is not int or not 1 <= data["quantity"] <= 1000:
                raise Problem(400, "invalid_stock", "Elegí un artículo de prueba y una cantidad entera de 1 a 1000.")
            payload = dict(sku=data["sku"], quantity=data["quantity"], note=text(data["note"], "note", 500), source="DEPOSITO-DEMO", destination=membership["site"])
            request = uuid.uuid4().hex
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,NULL,?,?)", (request, room, actor["id"], canonical(payload), digest(payload), "pending", now, now + 1800))
            self.audit(db, actor["id"], "stock.requested", request, room, {"payload_digest": digest(payload)})
            return {"id": request, "status": "pending", "executed": False}
        if len(action) == 3 and action[0] == "requests" and action[2] == "decision":
            fields(data, ("decision", "payload_digest"))
            if actor["kind"] != "human" or membership["role"] != "approver":
                raise Problem(403, "human_approver_required", "Se requiere una persona aprobadora de esta sala.")
            request = db.execute("SELECT * FROM requests WHERE id=? AND room_id=?", (action[1], room)).fetchone()
            if not request:
                raise Problem(404, "not_found", "Solicitud inexistente.")
            if request["actor_id"] == actor["id"]:
                raise Problem(403, "self_approval", "Otra persona debe revisar tu solicitud.")
            requester_active = db.execute("SELECT active FROM identities WHERE id=?", (request["actor_id"],)).fetchone()[0]
            if request["status"] != "pending" or now > request["expires_at"] or not requester_active:
                raise Problem(409, "not_pending", "La solicitud ya fue revisada o venció.")
            if data["payload_digest"] != request["payload_digest"]:
                raise Problem(409, "stale_approval", "La aprobación no corresponde a estos datos.")
            if data["decision"] not in ("approve", "reject"):
                raise Problem(400, "invalid_decision", "Decisión inválida.")
            status = "approved_unexecuted" if data["decision"] == "approve" else "rejected"
            db.execute("UPDATE requests SET status=?,reviewer=? WHERE id=?", (status, actor["id"], request["id"]))
            self.audit(db, actor["id"], "stock." + status, request["id"], room, {"payload_digest": request["payload_digest"]})
            return {"id": request["id"], "status": status, "executed": False}
        if action == ["tasks"]:
            fields(data, ("goal", "lead_id", "contributors"))
            if actor["kind"] != "human":
                raise Problem(403, "human_required", "Solo una persona puede iniciar una ronda.")
            goal = text(data["goal"], "goal", 2000)
            lead = text(data["lead_id"], "lead_id", 40)
            self.agent_ids(db, room, [lead])
            self.agent_ids(db, room, data["contributors"])
            if not data["contributors"] or lead in data["contributors"]:
                raise Problem(400, "invalid_agents", "Elegí un coordinador y de uno a cuatro colaboradores diferentes.")
            task = uuid.uuid4().hex
            db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,NULL,?,?)", (task, room, actor["id"], goal, lead, canonical(data["contributors"]), "collecting", now, now + 86400))
            self.audit(db, actor["id"], "task.created", task, room, {"lead_id": lead, "contributors": data["contributors"]})
            return {"id": task, "status": "collecting"}
        if len(action) == 3 and action[0] == "tasks" and action[2] in ("contributions", "synthesis"):
            fields(data, ("text",))
            self.agent_writer(actor)
            task = db.execute("SELECT * FROM tasks WHERE id=? AND room_id=?", (action[1], room)).fetchone()
            if not task:
                raise Problem(404, "not_found", "Encargo inexistente.")
            requester_active = db.execute("SELECT active FROM identities WHERE id=?", (task["actor_id"],)).fetchone()[0]
            if task["status"] == "completed" or now > task["expires_at"] or not requester_active:
                raise Problem(409, "task_closed", "La ronda terminó o venció.")
            content = text(data["text"], "text", 8000)
            contributors = json.loads(task["contributors"])
            if action[2] == "contributions":
                if actor["id"] not in contributors:
                    raise Problem(403, "not_assigned", "Esta cuenta no es colaboradora del encargo.")
                if db.execute("SELECT 1 FROM contributions WHERE task_id=? AND actor_id=?", (task["id"], actor["id"])).fetchone():
                    raise Problem(409, "already_contributed", "Ya existe un aporte de esta cuenta.")
                db.execute("INSERT INTO contributions VALUES(?,?,?,?)", (task["id"], actor["id"], content, now))
                count = db.execute("SELECT count(*) FROM contributions WHERE task_id=?", (task["id"],)).fetchone()[0]
                if count == len(contributors):
                    db.execute("UPDATE tasks SET status='ready_for_synthesis' WHERE id=?", (task["id"],))
            else:
                if actor["id"] != task["lead_id"]:
                    raise Problem(403, "not_coordinator", "Solo la cuenta coordinadora puede entregar la síntesis.")
                if task["status"] != "ready_for_synthesis":
                    raise Problem(409, "contributions_pending", "Faltan aportes de colaboradores.")
                db.execute("UPDATE tasks SET status='completed',synthesis=? WHERE id=?", (content, task["id"]))
            self.audit(db, actor["id"], "task." + action[2], task["id"], room, {"content_hash": digest(content)})
            return {"id": task["id"], "accepted": True, "stock_executed": False}
        raise Problem(404, "not_found", "Operación inexistente. No hay ejecución de stock.")

    def read(self, token, route, after=0):
        with self.connection() as db:
            actor = self.authenticate(db, token)
            if route == "/api/me":
                return actor
            if route == "/api/identities":
                if not actor["admin"] or actor["kind"] != "human":
                    raise Problem(403, "admin_required", "Solo para administración local.")
                return [dict(r) for r in db.execute("SELECT id,name,kind FROM identities WHERE active=1 ORDER BY name")]
            if route == "/api/rooms":
                return [dict(r) for r in db.execute("SELECT r.*,m.role FROM rooms r JOIN members m ON r.id=m.room_id WHERE m.actor_id=? ORDER BY r.name", (actor["id"],))]
            parts = route.strip("/").split("/")
            if len(parts) not in (3, 4) or parts[:2] != ["api", "rooms"]:
                raise Problem(404, "not_found", "Recurso inexistente.")
            room = parts[2]
            membership = self.member(db, actor, room)
            if len(parts) == 4 and parts[3] == "messages":
                rows = db.execute("SELECT * FROM messages WHERE room_id=? AND seq>? ORDER BY seq LIMIT 100", (room, after)).fetchall()
                return {"items": [self.message(r) for r in rows], "next_cursor": rows[-1]["seq"] if rows else after}
            if len(parts) == 4 and parts[3] == "audit":
                return [dict(r) for r in db.execute("SELECT * FROM audit WHERE room_id=? AND seq>? ORDER BY seq LIMIT 100", (room, after))]
            if len(parts) == 4 and parts[3] == "inbox":
                if actor["kind"] != "agent":
                    raise Problem(403, "agent_required", "Bandeja exclusiva de cuentas de agente.")
                # Fixed per-call bounds; last 24h tasks only. No automatic agent execution.
                messages = [self.message(r) for r in db.execute("SELECT * FROM messages m WHERE room_id=? AND seq>? AND created_at>? AND EXISTS(SELECT 1 FROM identities i WHERE i.id=m.actor_id AND i.active=1) AND NOT EXISTS(SELECT 1 FROM messages r WHERE r.reply_to=m.id AND r.actor_id=?) ORDER BY seq LIMIT 100", (room, after, time.time() - 86400, actor["id"]))]
                tasks = self.task_rows(db, room)
                active = {p["id"] for p in self.participants(db, room) if p["active"]}
                return {"messages": [m for m in messages if actor["id"] in m["targets"]], "next_cursor": messages[-1]["seq"] if messages else after,
                        "tasks": [t for t in tasks if t["actor_id"] in active and t["expires_at"] > time.time() and ((actor["id"] in t["contributors"] and actor["id"] not in [c["actor_id"] for c in t["contributions"]]) or (actor["id"] == t["lead_id"] and t["status"] == "ready_for_synthesis"))]}
            if len(parts) != 3:
                raise Problem(404, "not_found", "Recurso inexistente.")
            messages = [self.message(r) for r in db.execute("SELECT * FROM messages WHERE room_id=? ORDER BY seq DESC LIMIT 100", (room,))][::-1]
            requests = [dict(r) for r in db.execute("SELECT * FROM requests WHERE room_id=? ORDER BY created_at DESC LIMIT 100", (room,))]
            for r in requests:
                r["payload"] = json.loads(r["payload"])
                r["executed"] = False
            return {"id": room, **membership, "participants": self.participants(db, room), "messages": messages, "requests": requests, "tasks": self.task_rows(db, room), "integration": "unverified", "stock_execution": "unavailable"}

    @staticmethod
    def message(row):
        out = dict(row)
        out["targets"] = json.loads(out["targets"])
        return out

    @staticmethod
    def task_rows(db, room):
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks WHERE room_id=? ORDER BY created_at DESC LIMIT 100", (room,))]
        for task in tasks:
            task["contributors"] = json.loads(task["contributors"])
            task["contributions"] = [dict(r) for r in db.execute("SELECT actor_id,text,created_at FROM contributions WHERE task_id=? ORDER BY created_at", (task["id"],))]
        return tasks

    def verify_audit(self):
        with self.connection() as db:
            previous, count = "0" * 64, 0
            for row in db.execute("SELECT * FROM audit ORDER BY seq"):
                if row["prev_hash"] != previous or hashlib.sha256((previous + row["event"]).encode()).hexdigest() != row["hash"] or json.loads(row["event"]).get("room") != row["room_id"]:
                    raise Problem(409, "audit_invalid", "Se detectó una alteración de auditoría.")
                previous, count = row["hash"], count + 1
            return {"events": count, "head_hash": previous, "valid": True}
