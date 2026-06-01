"""Send / stop operators, worker thread, and timer bridge to the main bpy thread."""

from __future__ import annotations

import queue
import threading
from typing import Any, Optional

import bpy

from . import apply_actions, context_builder, ollama_client, system_prompt

ADDON_ID = "blender_gpt"

_result_queue: queue.Queue = queue.Queue(maxsize=4)
_cancel_event = threading.Event()
_worker_thread: Optional[threading.Thread] = None
_timer_handle: Optional[Any] = None
_pending_window_ptr: int = 0
_active_request_id: int = 0


def _worker_alive() -> bool:
    t = _worker_thread
    return t is not None and t.is_alive()


def _drain_result_queue() -> None:
    while True:
        try:
            _result_queue.get_nowait()
        except queue.Empty:
            break


def _finish_request(g: BlenderGPTState, status: str, *, response: str | None = None) -> None:
    g.busy = False
    g.status = status
    if response is not None:
        g.response = response


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
) -> None:
    try:
        text = ollama_client.chat_completion(
            base_url,
            model,
            system,
            user,
            num_ctx=num_ctx,
            cancel_event=_cancel_event,
        )
        _result_queue.put((request_id, "ok", text))
    except InterruptedError:
        _result_queue.put((request_id, "cancel", ""))
    except Exception as e:
        _result_queue.put((request_id, "err", str(e)))


def _timer_poll() -> Optional[float]:
    global _timer_handle, _worker_thread

    try:
        request_id, kind, data = _result_queue.get_nowait()
    except queue.Empty:
        if _worker_alive():
            return 0.15
        if _worker_thread is not None and not _worker_alive():
            _worker_thread = None
            wm = bpy.context.window_manager
            if hasattr(wm, "blender_gpt"):
                g = wm.blender_gpt
                if g.busy:
                    _finish_request(g, "Request ended without a response.")
        _timer_handle = None
        return None

    _worker_thread = None

    if request_id != _active_request_id:
        if _worker_alive():
            return 0.15
        _timer_handle = None
        return None

    window = _window_from_ptr(_pending_window_ptr)
    if window is None:
        for w in bpy.context.window_manager.windows:
            window = w
            break
    if window is None:
        _timer_handle = None
        return None

    scene = getattr(window, "scene", None) or bpy.context.scene
    view_layer = None
    if scene is not None and scene.view_layers:
        view_layer = scene.view_layers.active or scene.view_layers[0]

    wm = bpy.context.window_manager
    g = wm.blender_gpt

    override: dict[str, Any] = {"window": window, "scene": scene}
    if view_layer is not None:
        override["view_layer"] = view_layer

    if kind == "ok":
        g.response = data
        g.status = "Applying actions (if any)…"
        actions = apply_actions.extract_actions_json(data)
        with bpy.context.temp_override(**override):
            if actions:
                logs = apply_actions.apply_actions(bpy.context, actions)
                g.status = "Done. " + (" ".join(logs) if logs else "No structured actions applied.")
            else:
                g.status = "Done."
    elif kind == "cancel":
        g.status = "Cancelled."
    else:
        g.response = ""
        g.status = f"Error: {data}"

    g.busy = False
    _timer_handle = None
    return None


def _ensure_result_timer() -> None:
    global _timer_handle
    if _timer_handle is not None and bpy.app.timers.is_registered(_timer_handle):
        return
    _timer_handle = _timer_poll
    bpy.app.timers.register(_timer_poll, first_interval=0.12)


class BG_OT_send(bpy.types.Operator):
    bl_idname = "blender_gpt.send"
    bl_label = "Ask BlenderGPT"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context):
        global _worker_thread, _timer_handle, _pending_window_ptr, _active_request_id

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

        digest = context_builder.build_scene_digest(
            context, max_chars=int(prefs.max_context_chars)
        )
        user = system_prompt.build_user_message(digest, g.prompt)
        num_ctx = int(prefs.num_ctx) if prefs.num_ctx > 0 else 0

        _active_request_id += 1
        request_id = _active_request_id
        _cancel_event.clear()
        _drain_result_queue()

        g.busy = True
        g.status = "Calling Ollama…"
        w = context.window
        _pending_window_ptr = w.as_pointer() if w else 0

        t = threading.Thread(
            target=_worker_main,
            args=(request_id,),
            kwargs={
                "base_url": prefs.base_url,
                "model": prefs.model,
                "num_ctx": num_ctx,
                "system": system_prompt.SYSTEM_PROMPT,
                "user": user,
            },
            daemon=True,
        )
        _worker_thread = t
        t.start()

        _ensure_result_timer()
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
        wm = context.window_manager
        g = wm.blender_gpt
        _finish_request(
            g,
            "Cancelled. (Ollama may still finish in the background; you can send a new prompt.)",
        )
        _drain_result_queue()
        _ensure_result_timer()
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
        ok = ollama_client.check_connection(prefs.base_url)
        if ok:
            self.report({"INFO"}, "Ollama reachable.")
        else:
            self.report({"ERROR"}, "Cannot reach Ollama at " + prefs.base_url)
        return {"FINISHED"}


classes = (
    BlenderGPTState,
    BG_OT_send,
    BG_OT_stop,
    BG_OT_reset,
    BG_OT_ping,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.blender_gpt = bpy.props.PointerProperty(type=BlenderGPTState)


def unregister():
    global _timer_handle
    if _timer_handle is not None and bpy.app.timers.is_registered(_timer_handle):
        bpy.app.timers.unregister(_timer_handle)
    _timer_handle = None
    del bpy.types.WindowManager.blender_gpt
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
