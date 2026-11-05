import argparse
import json
import os
from pathlib import Path

from .core import Problem, Store
from .server import make_server


def private_file(path, content):
    with os.fdopen(os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
        out.write(content)


def main():
    parser = argparse.ArgumentParser(description="GL Sala · prototipo local, sin conexiones externas")
    parser.add_argument("--data", type=Path, default=Path(".local"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-demo")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    identity = commands.add_parser("add-identity")
    identity.add_argument("--name", required=True)
    identity.add_argument("--kind", choices=("human", "agent"), default="human")
    identity.add_argument("--agent-write", action="store_true", help="Habilita respuestas locales de esta cuenta de agente; no conecta Muse")
    revoke = commands.add_parser("revoke")
    revoke.add_argument("identity_id")
    commands.add_parser("verify-audit")
    args = parser.parse_args()
    os.umask(0o077)
    args.data.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = args.data / "room.sqlite3"
    if args.command == "init-demo" and database.exists():
        parser.error("Ya existe una base. No se sobrescribió; usá otro directorio --data para otra demo.")
    if args.command != "init-demo" and not database.exists():
        parser.error("Primero ejecutá: python3 -m muse_room init-demo")
    store = Store(database)
    if args.command == "init-demo":
        specs = [("Parker · demo", "human", True), ("Personal Show · demo", "human", False),
                 ("Supervisor · demo", "human", False), ("Muse_HQ · cuenta pendiente", "agent", False),
                 ("Agente colaborador · reserva", "agent", False)]
        access = []
        for name, kind, admin in specs:
            actor, token = store.create_identity(name, kind, admin)
            access.append(dict(id=actor, name=name, kind=kind, token=token))
        group = store.mutate(access[0]["token"], "/api/rooms", "seed-show-room", {
            "name": "Show · Equipo", "site": "SHOW-DEMO", "members": [
                {"id": access[1]["id"], "role": "member"}, {"id": access[2]["id"], "role": "approver"},
                {"id": access[3]["id"], "role": "member"}]})
        lab = store.mutate(access[0]["token"], "/api/rooms", "seed-agents-room", {
            "name": "Laboratorio · Agentes", "site": "LAB-DEMO", "members": [
                {"id": access[3]["id"], "role": "member"}, {"id": access[4]["id"], "role": "member"}]})
        private_file(args.data / "demo-access.json", json.dumps({"identities": access, "rooms": [group, lab]}, indent=2, ensure_ascii=False))
        private_file(args.data / "demo-access.txt", "CLAVES DE PRUEBA LOCAL. No publicar ni dar claves humanas a agentes.\n\n" + "\n\n".join(a["name"] + "\n" + a["token"] for a in access) + "\n")
        print("Demo creada. Claves individuales en " + str(args.data / "demo-access.txt") + ". Cuentas de agente: solo lectura, conexión no verificada.")
    elif args.command == "add-identity":
        actor, token = store.create_identity(args.name, args.kind, agent_write=args.agent_write)
        path = args.data / ("access-" + actor + ".json")
        private_file(path, json.dumps(dict(id=actor, name=args.name, token=token), indent=2))
        print("Identidad creada. Clave privada local en " + str(path))
    elif args.command == "revoke":
        store.revoke(args.identity_id)
        print("Identidad revocada. Su clave ya no permite leer ni escribir.")
    elif args.command == "verify-audit":
        print(json.dumps(store.verify_audit(), indent=2))
    else:
        server = make_server(store, args.port)
        print("GL Sala local: http://127.0.0.1:" + str(server.server_port), flush=True)
        print("Solo este equipo. Muse, WhatsApp y stock no están conectados.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Problem as exc:
        raise SystemExit(exc.message)
