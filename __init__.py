# legacy metadata... (Blender removes this before registering an extension, so runtime code uses ADDON_VERSION)
ADDON_VERSION = (5, 1, 0)

bl_info = {
    "name": "Mr Mannequins Tools",
    "author": "James Goldsworthy (Jim Kroovy)",
    # keep this literal... (the legacy scanner reads bl_info with ast.literal_eval and never imports us)
    "version": (5, 1, 0),
    "blender": (5, 0, 0),
    "location": "3D Viewport > Pose",
    "description": "Rigging, mesh and export tools for (almost) any character.",
    "category": "Armatures",
}

import addon_utils
import bpy

from . import utilities, rigging, retargeting, orientation, shaping, skinning, keyframing, importing, exporting, templates

_DOMAINS = (
    utilities,
    orientation,
    rigging,
    retargeting,
    shaping,
    skinning,
    keyframing,
    importing,
    exporting,
    templates,
)

_MENUS = (
    bpy.types.VIEW3D_MT_object_apply,
    bpy.types.VIEW3D_MT_pose,
    bpy.types.VIEW3D_MT_pose_apply,
    bpy.types.VIEW3D_MT_object,
    bpy.types.VIEW3D_MT_edit_mesh_vertices,
    bpy.types.VIEW3D_MT_paint_weight,
    bpy.types.DOPESHEET_MT_key,
    bpy.types.TOPBAR_MT_file_import,
    bpy.types.TOPBAR_MT_file_export,
    bpy.types.VIEW3D_MT_add,
)


def _is_mmt_module(module_name):
    """true if the module name is exactly a legacy or extension root..."""
    if module_name == "mr_mannequins_tools":
        return True
    parts = module_name.split(".")
    return len(parts) == 3 and parts[0] == "bl_ext" and parts[2] == "mr_mannequins_tools"


def _remove_enabled_preference(module_name):
    addon = bpy.context.preferences.addons.get(module_name)
    if addon is not None:
        bpy.context.preferences.addons.remove(addon)


def _disable_other_installations():
    """migrate from the other packaging form before registering..."""
    current = __name__
    others = [
        addon.module for addon in bpy.context.preferences.addons
        if addon.module != current and _is_mmt_module(addon.module)
    ]
    for module_name in others:
        errors = []
        addon_utils.disable(
            module_name,
            default_set=True,
            handle_error=errors.append,
        )
        # raise the first error and attach the rest as notes...
        if errors:
            error = errors[0]
            for cleanup_error in errors[1:]:
                error.add_note(f"Additional error while disabling {module_name}: {cleanup_error!r}")
            raise error
        if bpy.context.preferences.addons.get(module_name) is not None:
            raise RuntimeError(f"Could not disable the other Mr Mannequins Tools installation: {module_name}")


def _registered_classes(domain):
    """find rna classes still owned by one of our domain modules..."""
    prefix = domain.__name__ + "."
    classes = []
    for value in vars(domain).values():
        if not hasattr(value, "__dict__"):
            continue
        for candidate in vars(value).values():
            if (
                isinstance(candidate, type)
                and candidate.__module__.startswith(prefix)
                and getattr(candidate, "is_registered", False)
                and candidate not in classes
            ):
                classes.append(candidate)
    return classes


def _restore_deferred_paint_swaps():
    if not hasattr(bpy.data, "objects"):
        return 0.1
    swaps = skinning.functions.get_paint_swaps()
    if swaps:
        skinning.functions.set_paint_left(swaps)
    return None


def _recover_interrupted_registration():
    """recover the cached submodule state left by a failed older extension..."""
    dirty = [domain for domain in _DOMAINS if _registered_classes(domain)]
    if not dirty:
        return
    errors = []
    for domain in reversed(_DOMAINS):
        if domain not in dirty:
            continue
        try:
            # an old skinning unregister reads bpy.data during extension install... (handlers and rna still go now, only the weight paint restore waits)
            if domain is skinning and not hasattr(bpy.data, "objects"):
                get_paint_swaps = domain.functions.get_paint_swaps
                domain.functions.get_paint_swaps = lambda: []
                try:
                    domain.unregister()
                finally:
                    domain.functions.get_paint_swaps = get_paint_swaps
                if not bpy.app.timers.is_registered(_restore_deferred_paint_swaps):
                    bpy.app.timers.register(_restore_deferred_paint_swaps, first_interval=0.0)
            else:
                domain.unregister()
        except Exception as error:
            errors.append((domain.__name__, error))
    remaining = [cls for domain in _DOMAINS for cls in _registered_classes(domain)]
    # raise if the cleanup left anything behind...
    if errors or remaining:
        details = [f"{name}: {error!r}" for name, error in errors]
        details.extend(f"still registered: {cls.__module__}.{cls.__name__}" for cls in remaining)
        raise RuntimeError(
            "Could not safely recover an interrupted Mr Mannequins Tools registration; "
            + "; ".join(details)
        ) from (errors[0][1] if errors else None)


def _capture_domain_state(domain):
    return {
        "menus": {menu: tuple(getattr(menu.draw, "_draw_funcs", ())) for menu in _MENUS},
        "depsgraph_handlers": tuple(bpy.app.handlers.depsgraph_update_post),
        "load_handlers": tuple(bpy.app.handlers.load_post),
        "armature_mmt": hasattr(bpy.types.Armature, "mmt"),
        "pose_bone_mmt": hasattr(bpy.types.PoseBone, "mmt"),
        "keymaps": len(getattr(domain, "_keymaps", ())),
    }


def _cleanup_failed_domain(domain, state, classes):
    """remove only what the failed register call added..."""
    errors = []
    # menus...
    for menu, previous in state["menus"].items():
        for callback in tuple(getattr(menu.draw, "_draw_funcs", ())):
            if callback not in previous:
                try:
                    menu.remove(callback)
                except Exception as error:
                    errors.append(error)
    # handlers...
    for handlers, previous in (
        (bpy.app.handlers.depsgraph_update_post, state["depsgraph_handlers"]),
        (bpy.app.handlers.load_post, state["load_handlers"]),
    ):
        for handler in tuple(handlers):
            if handler not in previous:
                try:
                    handlers.remove(handler)
                except Exception as error:
                    errors.append(error)
    keymaps = getattr(domain, "_keymaps", None)
    # keymaps added by the failed call come off in reverse...
    if keymaps is not None:
        for keymap, keymap_item in reversed(keymaps[state["keymaps"]:]):
            try:
                keymap.keymap_items.remove(keymap_item)
            except Exception as error:
                errors.append(error)
        del keymaps[state["keymaps"]:]
    # pointers...
    for owner, name, existed in (
        (bpy.types.Armature, "mmt", state["armature_mmt"]),
        (bpy.types.PoseBone, "mmt", state["pose_bone_mmt"]),
    ):
        if not existed and hasattr(owner, name):
            try:
                delattr(owner, name)
            except Exception as error:
                errors.append(error)
    # classes...
    for cls in reversed(classes):
        if getattr(cls, "is_registered", False):
            try:
                bpy.utils.unregister_class(cls)
            except Exception as error:
                errors.append(error)
    return errors


def register():
    # never mix legacy and extension classes... (the old copy cleans itself up before we register anything)
    _disable_other_installations()
    _recover_interrupted_registration()

    registered = []
    active = None
    active_classes = []
    active_state = None
    try:
        # load shared addon preferences then domain subpackages in dependency order...
        for active in _DOMAINS:
            active_classes = []
            active_state = _capture_domain_state(active)
            register_class = active.register_class

            def tracked_register_class(cls):
                register_class(cls)
                active_classes.append(cls)

            active.register_class = tracked_register_class
            try:
                active.register()
            finally:
                active.register_class = register_class
            registered.append(active)
        active = None

        # preferences survive an install over, so reset settings from another schema...
        prefs = utilities.functions.get_addon_preferences(bpy.context)
        version = ".".join(str(n) for n in ADDON_VERSION)
        if prefs.version != version:
            prefs.import_settings, prefs.export_settings, prefs.version = "", "", version
    except Exception as error:
        cleanup_errors = []
        # a domain may have failed part way... (its own unregister gets first go at unwinding it)
        if active is not None:
            try:
                active.unregister()
            except Exception as cleanup_error:
                cleanup_errors.append((active.__name__, cleanup_error))
            for cleanup_error in _cleanup_failed_domain(active, active_state, active_classes):
                cleanup_errors.append((active.__name__, cleanup_error))
        for domain in reversed(registered):
            try:
                domain.unregister()
            except Exception as cleanup_error:
                cleanup_errors.append((domain.__name__, cleanup_error))
        _remove_enabled_preference(__name__)
        for name, cleanup_error in cleanup_errors:
            error.add_note(f"Rollback error in {name}: {cleanup_error!r}")
        raise

def unregister():
    errors = []
    for domain in reversed(_DOMAINS):
        try:
            domain.unregister()
        except Exception as error:
            errors.append((domain.__name__, error))
    # report everything that failed to clean up at once...
    if errors:
        details = "; ".join(f"{name}: {cleanup_error!r}" for name, cleanup_error in errors)
        error = RuntimeError(f"Mr Mannequins Tools did not unregister cleanly: {details}")
        for name, cleanup_error in errors:
            error.add_note(f"Unregister error in {name}: {cleanup_error!r}")
        raise error from errors[0][1]
