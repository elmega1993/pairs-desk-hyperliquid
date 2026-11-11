"""Read-only Desk inference via the signed-in Codex app-server."""
import json
import os
import selectors
import shutil
import subprocess
import tempfile
import time

from .memory import _SECRET


class CodexProviderError(Exception):
    pass


class CodexProvider:
    def __init__(self, model="gpt-5.6-sol"):
        self.model = model

    @staticmethod
    def environment():
        # Do not inherit API keys, custom endpoints or the parent agent's session.
        return {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "XDG_RUNTIME_DIR")
                if key in os.environ}

    def available(self):
        try:
            result = subprocess.run(
                ["codex", "login", "status"], env=self.environment(),
                capture_output=True, timeout=5, text=True, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0 and "Logged in using ChatGPT" in result.stdout + result.stderr

    def answer(self, messages):
        if any(_SECRET.search(message["content"]) for message in messages):
            raise CodexProviderError("El contexto contiene posibles credenciales. Quitalas antes de enviarlo.")
        executable = shutil.which("codex")
        if not executable:
            raise CodexProviderError("Codex CLI no está instalado.")
        args = [executable, "app-server", "--listen", "stdio://",
                "--disable", "shell_tool", "--disable", "unified_exec",
                "--disable", "plugins", "--disable", "apps", "--disable", "goals",
                "--disable", "multi_agent", "--disable", "skill_search", "--disable", "tool_suggest",
                "-c", 'model_provider="openai"', "-c", 'forced_login_method="chatgpt"',
                "-c", 'web_search="disabled"', "-c", "mcp_servers={}",
                "-c", "project_doc_max_bytes=0",
                "-c", 'default_permissions="pair-desk"',
                "-c", 'permissions.pair-desk.filesystem={":minimal"="read"}',
                "-c", "permissions.pair-desk.network.enabled=false"]
        try:
            with tempfile.TemporaryDirectory(prefix="pair-desk-codex-") as cwd:
                with subprocess.Popen(
                    args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    cwd=cwd, env=self.environment(),
                ) as process:
                    try:
                        return self._turn(process, cwd, messages)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                process.kill()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CodexProviderError("No se pudo completar la consulta con Codex.") from exc

    def _turn(self, process, cwd, messages):
        deadline = time.monotonic() + 180
        buffer = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)

            def send(method, params=None, request_id=None):
                packet = {"method": method}
                if params is not None:
                    packet["params"] = params
                if request_id is not None:
                    packet["id"] = request_id
                process.stdin.write(json.dumps(packet).encode() + b"\n")
                process.stdin.flush()

            def receive():
                while time.monotonic() < deadline:
                    end = buffer.find(b"\n")
                    if end >= 0:
                        line = bytes(buffer[:end])
                        del buffer[:end + 1]
                        return json.loads(line)
                    if not selector.select(max(0, deadline - time.monotonic())):
                        break
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        raise CodexProviderError("Codex cerró la conexión. Revisá su inicio de sesión.")
                    buffer.extend(chunk)
                    if len(buffer) > 2_000_000:
                        raise CodexProviderError("Codex devolvió un evento demasiado grande.")
                raise CodexProviderError("Codex alcanzó el límite de tiempo de la consulta.")

            def rpc(method, params, request_id):
                send(method, params, request_id)
                while True:
                    packet = receive()
                    if packet.get("id") == request_id and "method" not in packet:
                        if "error" in packet:
                            raise CodexProviderError(f"Codex rechazó la operación {method}. Revisá el acceso y el cupo de tu plan.")
                        return packet["result"]
                    if "id" in packet and "method" in packet:
                        raise CodexProviderError("Codex solicitó una operación fuera de los permisos del asesor.")

            rpc("initialize", {"clientInfo": {"name": "pair_desk", "version": "1.0"},
                               "capabilities": {"experimentalApi": True}}, 1)
            send("initialized")
            account = rpc("account/read", {"refreshToken": False}, 2).get("account") or {}
            if account.get("type") != "chatgpt":
                raise CodexProviderError("Iniciá sesión en Codex con tu cuenta de ChatGPT.")
            if rpc("mcpServerStatus/list", {"limit": 1}, 3).get("data"):
                raise CodexProviderError("El perfil del asesor requiere que los conectores de Codex estén deshabilitados.")
            session = rpc("thread/start", {
                "model": self.model, "cwd": cwd, "approvalPolicy": "never",
                "ephemeral": True, "baseInstructions": messages[0]["content"],
                "developerInstructions": "Respondé como asesor de Pair Desk. Usá la evidencia incluida en la consulta. No ejecutes comandos ni uses archivos o conectores.",
            }, 4)
            if session.get("instructionSources"):
                raise CodexProviderError("Codex cargó instrucciones externas al asesor.")
            thread = session["thread"]
            send("turn/start", {
                "threadId": thread["id"], "effort": "medium",
                "input": [{"type": "text", "text": json.dumps(messages[1:], ensure_ascii=False),
                           "text_elements": []}],
            }, 5)
            answer = ""
            while True:
                packet = receive()
                if "id" in packet and "method" in packet:
                    raise CodexProviderError("Codex solicitó una operación fuera de los permisos del asesor.")
                if packet.get("id") == 5 and "error" in packet:
                    raise CodexProviderError("Codex no pudo iniciar la consulta. Revisá el acceso y el cupo de Plus.")
                params = packet.get("params", {})
                if params.get("threadId") != thread["id"]:
                    continue
                if packet.get("method") == "item/started":
                    if params.get("item", {}).get("type") in {
                        "commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall",
                        "webSearch", "collabAgentToolCall",
                    }:
                        raise CodexProviderError("Codex intentó usar una herramienta fuera del asesor.")
                if packet.get("method") == "item/completed":
                    item = params.get("item", {})
                    if item.get("type") == "agentMessage" and item.get("phase") != "commentary":
                        answer = item.get("text", "")
                if packet.get("method") == "turn/completed":
                    turn = params["turn"]
                    if turn["status"] != "completed" or not answer.strip():
                        detail = (turn.get("error") or {}).get("message", "")
                        if "model_not_found" in detail:
                            raise CodexProviderError("El modelo configurado no está habilitado en tu sesión de Codex.")
                        raise CodexProviderError("Codex no completó la respuesta. Revisá el estado de la sesión y su cupo.")
                    if _SECRET.search(answer):
                        raise CodexProviderError("La respuesta contiene posibles credenciales.")
                    return answer
