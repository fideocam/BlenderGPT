"""Send / stop operators, worker thread, and timer bridge to the main bpy thread."""

from __future__ import annotations

import queue
import threading
import time
import traceback
from typing import Any, Optional

import bpy

from . import apply_actions, context_builder, ollama_client, system_prompt

ADDON_ID = "blender_gpt"

_result_queue: queue.Queue = queue.Queue(maxsize=256)
_progress_queue: queue.Queue = queue.Queue(maxsize=64)
_cancel_event = threading.Event()
_worker_thread: Optional[threading.Thread] = None
_pending_window_ptr: int = 0
_active_request_id: int = 0
_request_started: float = 0.0
_poll_timer_registered: bool = False


def _log(message: str) -> None:
    print(f"BlenderGPT: {message}")


def _worker_alive() -> bool:
    t = _worker_thread
    return t is not None and t.is_alive()


def _drain_result_queue() -> None:
    while True:
        try:
            _result_queue.get_nowait()
        except queue.Empty:
            break


def _drain_progress_queue() -> None:
    while True:
        try:
            _progress_queue.get_nowait()
        except queue.Empty:
            break


def _enqueue_result(item: tuple) -> None:
    kind = item[1] if len(item) > 1 else None
    if kind == "stream":
        # Drop old stream tokens rather than blocking; the final "ok" carries the full text
        try:
            _result_queue.put_nowait(item)
        except queue.Full:
            pass
        return
    try:
        _result_queue.put_nowait(item)
    except queue.Full:
        _drain_result_queue()
        _result_queue.put_nowait(item)


def _set_phase(message: str) -> None:
    try:
        _progress_queue.put_nowait(message)
    except queue.Full:
        pass


def _finish_request(g: BlenderGPTState, status: str, *, response: str | None = None) -> None:
    g.busy = False
    g.status = status
    if response is not None:
        g.response = response
    _redraw_addon_ui()
    _log(status)


def _redraw_addon_ui() -> None:
    """Panels do not refresh when properties change from timers or worker threads."""
    wm = bpy.context.window_manager
    if wm is None:
        return
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            area.tag_redraw()
            for region in area.regions:
                region.tag_redraw()


def _addon_preferences(context: bpy.types.Context):
    addon = context.preferences.addons.get(ADDON_ID)
    if addon is None:
        return None
    return addon.preferences


class BlenderGPTState(bpy.types.PropertyGroup):
    prompt: bpy.props.StringProperty(
        name="Prompt",
        default="",
        maxlen=65536,
        description="Message to send with the scene digest",
    )
    response: bpy.props.StringProperty(
        name="Response",
        default="",
        maxlen=262144,
        description="Last assistant reply",
    )
    status: bpy.props.StringProperty(
        name="Status",
        default="",
        maxlen=4096,
    )
    busy: bpy.props.BoolProperty(name="Busy", default=False)


def _window_from_ptr(ptr: int) -> Optional[bpy.types.Window]:
    if not ptr:
        return None
    wm = bpy.context.window_manager
    for w in wm.windows:
        if w.as_pointer() == ptr:
            return w
    return None


def _worker_main(
    request_id: int,
    base_url: str,
    model: str,
    num_ctx: int,
    system: str,
    user: str,
    timeout: float,
    auto_wake: bool,
    preload_model: bool,
) -> None:
    try:
        _log(
            f"worker start id={request_id} model={model!r} "
            f"user_chars={len(user)} system_chars={len(system)}"
        )
        if auto_wake or preload_model:
            _set_phase("Connecting to Ollama…")
            ollama_client.ensure_ollama_ready(
                base_url,
                model,
                preload_model=preload_model,
                num_ctx=num_ctx,
                try_launch=auto_wake,
                cancel_event=_cancel_event,
            )
        _set_phase("Waiting for Ollama reply…")

        def _on_token(partial: str) -> None:
            _set_phase(f"Receiving… ({len(partial)} chars)")
            _enqueue_result((request_id, "stream", partial))

        text = ollama_client.chat_completion(
            base_url,
            model,
            system,
            user,
            num_ctx=num_ctx,
            cancel_event=_cancel_event,
            timeout=timeout,
            progress_cb=_on_token,
        )
        _log(f"worker ok id={request_id} reply_chars={len(text)}")
        _enqueue_result((request_id, "ok", text))
    except InterruptedError:
        _log(f"worker cancelled id={request_id}")
        _enqueue_result((request_id, "cancel", ""))
    except Exception as e:
        _log(f"worker error id={request_id}: {e}")
        traceback.print_exc()
        _enqueue_result((request_id, "err", str(e)))


def _context_override_for_window() -> dict[str, Any]:
    window = _window_from_ptr(_pending_window_ptr)
    if window is None:
        wm = bpy.context.window_manager
        if wm and wm.windows:
            window = wm.windows[0]
    if window is None:
        return {}
    scene = getattr(window, "scene", None) or bpy.context.scene
    override: dict[str, Any] = {"window": window, "scene": scene}
    if scene is not None and scene.view_layers:
        # scene.view_layers has no .active in Blender 4.x — use the window's view_layer
        vl = getattr(window, "view_layer", None)
        if vl is None:
            vl = scene.view_layers[0]
        override["view_layer"] = vl
    return override


def _deliver_result(context: bpy.types.Context, request_id: int, kind: str, data: str) -> None:
    g = context.window_manager.blender_gpt
    try:
        if kind == "ok":
            g.response = data or "(empty reply)"
            g.status = "Applying actions (if any)…"
            _redraw_addon_ui()
            actions = apply_actions.extract_actions_json(data)
            override = _context_override_for_window()
            if actions and override:
                with bpy.context.temp_override(**override):
                    logs = apply_actions.apply_actions(bpy.context, actions)
                g.status = "Done. " + (" ".join(logs) if logs else "No structured actions applied.")
            elif actions:
                logs = apply_actions.apply_actions(context, actions)
                g.status = "Done. " + (" ".join(logs) if logs else "No structured actions applied.")
            else:
                g.status = "Done."
        elif kind == "cancel":
            g.status = "Cancelled."
        else:
            g.response = ""
            g.status = f"Error: {data}"
    except Exception as e:
        g.response = ""
        g.status = f"Error: {e}"
        traceback.print_exc()
    finally:
        g.busy = False
        _redraw_addon_ui()
        _log(f"delivered id={request_id} status={g.status!r}")


def _apply_progress_updates(g: BlenderGPTState) -> None:
    updated = False
    while True:
        try:
            msg = _progress_queue.get_nowait()
        except queue.Empty:
            break
        if msg and g.status != msg:
            g.status = msg
            updated = True
    if updated:
        _redraw_addon_ui()


def _poll_worker_once(context: bpy.types.Context) -> bool:
    """Check worker/queue once. Returns True when polling should stop."""
    global _worker_thread, _request_started

    if not hasattr(context.window_manager, "blender_gpt"):
        _log("poll: blender_gpt state missing on WindowManager")
        return True

    g = context.window_manager.blender_gpt
    _apply_progress_updates(g)

    try:
        request_id, kind, data = _result_queue.get_nowait()
    except queue.Empty:
        if _worker_alive():
            elapsed = int(time.monotonic() - _request_started) if _request_started else 0
            waiting = g.status or "Waiting for Ollama…"
            if elapsed > 0 and f"({elapsed}s)" not in waiting:
                waiting = f"{waiting.rstrip('.')} ({elapsed}s)"
            if elapsed > 120 and "loading" not in waiting.lower():
                waiting += " — still loading model?"
            if g.status != waiting:
                g.status = waiting
                _redraw_addon_ui()
            return False
        if _worker_thread is not None and not _worker_alive():
            _worker_thread = None
            if g.busy:
                _finish_request(g, "Request ended without a response. See System Console.")
        return True

    if request_id != _active_request_id:
        _log(f"poll: stale result id={request_id} active={_active_request_id}")
        return not _worker_alive()

    if kind == "stream":
        # Live token update — don't stop polling
        g = context.window_manager.blender_gpt
        g.response = data
        _redraw_addon_ui()
        return False

    _worker_thread = None
    _deliver_result(context, request_id, kind, data)
    return True


def _app_timer_poll() -> Optional[float]:
    global _poll_timer_registered
    try:
        ctx = bpy.context
        if ctx is None:
            return 0.12
        if _poll_worker_once(ctx):
            _poll_timer_registered = False
            return None
    except Exception as e:
        _log(f"poll error: {e}")
        traceback.print_exc()
        try:
            g = bpy.context.window_manager.blender_gpt
            _finish_request(g, f"Error: {e}")
        except Exception:
            pass
        _poll_timer_registered = False
        return None
    return 0.12


def _start_polling() -> None:
    global _poll_timer_registered
    if _poll_timer_registered:
        try:
            if bpy.app.timers.is_registered(_app_timer_poll):
                bpy.app.timers.unregister(_app_timer_poll)
        except Exception:
            pass
    _poll_timer_registered = True
    bpy.app.timers.register(_app_timer_poll, first_interval=0.05)
    _log("poll timer started")


class BG_OT_send(bpy.types.Operator):
    bl_idname = "blender_gpt.send"
    bl_label = "Ask BlenderGPT"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context):
        global _worker_thread, _pending_window_ptr, _active_request_id, _request_started

        prefs = _addon_preferences(context)
        if prefs is None:
            self.report({"ERROR"}, "Addon preferences not found.")
            return {"CANCELLED"}

        wm = context.window_manager
        g = wm.blender_gpt
        if g.busy and _worker_alive():
            self.report({"WARNING"}, "Already busy.")
            return {"CANCELLED"}
        if g.busy:
            g.busy = False

        if not (g.prompt or "").strip():
            self.report({"WARNING"}, "Prompt is empty.")
            return {"CANCELLED"}

        try:
            model = ollama_client.resolve_model_name(prefs.base_url, prefs.model)
        except Exception as e:
            self.report({"ERROR"}, str(e))
            _log(str(e))
            return {"CANCELLED"}

        digest = context_builder.build_scene_digest(
            context, max_chars=int(prefs.max_context_chars)
        )
        user = system_prompt.build_user_message(digest, g.prompt)
        num_ctx = int(prefs.num_ctx) if prefs.num_ctx > 0 else 0
        timeout = float(getattr(prefs, "request_timeout", 600) or 600)

        _active_request_id += 1
        request_id = _active_request_id
        _cancel_event.clear()
        _drain_result_queue()
        _drain_progress_queue()

        g.busy = True
        g.status = "Connecting to Ollama…"
        g.response = ""
        _request_started = time.monotonic()
        w = context.window
        _pending_window_ptr = w.as_pointer() if w else 0
        _redraw_addon_ui()

        t = threading.Thread(
            target=_worker_main,
            args=(request_id,),
            kwargs={
                "base_url": prefs.base_url,
                "model": model,
                "num_ctx": num_ctx,
                "system": system_prompt.SYSTEM_PROMPT,
                "user": user,
                "timeout": timeout,
                "auto_wake": bool(getattr(prefs, "auto_wake_ollama", True)),
                "preload_model": bool(getattr(prefs, "preload_model", False)),
            },
            daemon=True,
        )
        _worker_thread = t
        t.start()

        _start_polling()
        self.report({"INFO"}, f"Asking {model}… (see Response below when done)")
        return {"FINISHED"}


class BG_OT_stop(bpy.types.Operator):
    bl_idname = "blender_gpt.stop"
    bl_label = "Stop BlenderGPT"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        g = context.window_manager.blender_gpt
        return g.busy

    def execute(self, context: bpy.types.Context):
        global _active_request_id

        _active_request_id += 1
        _cancel_event.set()
        g = context.window_manager.blender_gpt
        _finish_request(g, "Cancelled.")
        _drain_result_queue()
        return {"FINISHED"}


class BG_OT_reset(bpy.types.Operator):
    bl_idname = "blender_gpt.reset"
    bl_label = "Reset BlenderGPT"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context):
        global _active_request_id

        _active_request_id += 1
        _cancel_event.set()
        _drain_result_queue()
        _drain_progress_queue()
        g = context.window_manager.blender_gpt
        _finish_request(g, "")
        self.report({"INFO"}, "BlenderGPT state cleared.")
        return {"FINISHED"}


class BG_OT_ping(bpy.types.Operator):
    bl_idname = "blender_gpt.ping"
    bl_label = "Test Ollama connection"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context):
        prefs = _addon_preferences(context)
        if prefs is None:
            self.report({"ERROR"}, "Addon preferences not found.")
            return {"CANCELLED"}
        try:
            model = ollama_client.resolve_model_name(prefs.base_url, prefs.model)
            ollama_client.ensure_ollama_ready(
                prefs.base_url,
                model,
                preload_model=bool(getattr(prefs, "preload_model", False)),
                num_ctx=int(prefs.num_ctx) if prefs.num_ctx > 0 else 0,
                try_launch=bool(getattr(prefs, "auto_wake_ollama", True)),
            )
            self.report({"INFO"}, f"Ollama ready — model {model}")
        except Exception as e:
            self.report({"ERROR"}, str(e))
            _log(str(e))
            return {"CANCELLED"}
        return {"FINISHED"}


class BG_OT_sync_context(bpy.types.Operator):
    bl_idname = "blender_gpt.sync_context"
    bl_label = "Sync context from model"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context):
        prefs = _addon_preferences(context)
        if prefs is None:
            self.report({"ERROR"}, "Addon preferences not found.")
            return {"CANCELLED"}
        model = (prefs.model or "").strip()
        if not model:
            self.report({"WARNING"}, "Set a model name first.")
            return {"CANCELLED"}
        if not ollama_client.check_connection(prefs.base_url):
            self.report({"ERROR"}, "Cannot reach Ollama at " + prefs.base_url)
            return {"CANCELLED"}
        try:
            resolved = ollama_client.resolve_model_name(prefs.base_url, model)
            info = ollama_client.get_model_context_settings(prefs.base_url, resolved)
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        num_ctx = int(info["num_ctx"])
        max_scene = int(info["max_scene_chars"])
        if num_ctx > 0:
            prefs.num_ctx = num_ctx
        prefs.max_context_chars = max_scene
        prefs.context_hint = str(info.get("summary", ""))
        self.report({"INFO"}, prefs.context_hint[:240])
        return {"FINISHED"}


classes = (
    BlenderGPTState,
    BG_OT_send,
    BG_OT_stop,
    BG_OT_reset,
    BG_OT_ping,
    BG_OT_sync_context,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.blender_gpt = bpy.props.PointerProperty(type=BlenderGPTState)


def unregister():
    global _poll_timer_registered
    if _poll_timer_registered:
        try:
            if bpy.app.timers.is_registered(_app_timer_poll):
                bpy.app.timers.unregister(_app_timer_poll)
        except Exception:
            pass
    _poll_timer_registered = False
    del bpy.types.WindowManager.blender_gpt
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
