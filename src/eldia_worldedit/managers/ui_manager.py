"""Interactive Bedrock Form UI menus for WorldEdit (/we gui)."""

from __future__ import annotations

from typing import Any

from endstone.form import ActionForm, ModalForm, Slider, TextInput, Toggle


class UIManager:
    """Builds and opens native Bedrock ActionForm / ModalForm workflows."""

    def open_main_menu(self, player: Any, session_summary: str) -> None:
        """Open the top-level WorldEdit control panel for a Bedrock player."""
        form = ActionForm(
            title="§l§6Eldia WorldEdit",
            content=f"§7{session_summary}",
            on_submit=lambda p, idx: self._on_main_choice(p, idx),
        )
        form.add_button("Selection Tools\n§8pos1, pos2, expand, drawsel")
        form.add_button("Region Operations\n§8set, replace, walls, smooth")
        form.add_button("Shapes and Generators\n§8sphere, cyl, pyramid, forest")
        form.add_button("Clipboard and Schematics\n§8copy, paste, rotate, save")
        form.add_button("Brushes and Item Tools\n§8sphere brush, super pickaxe")
        form.add_button("History and Preferences\n§8undo, redo, fast mode, limit")
        player.send_form(form)

    def _on_main_choice(self, player: Any, index: int) -> None:
        if index == 0:
            self._open_selection_menu(player)
        elif index == 1:
            self._open_region_modal(player)
        elif index == 2:
            self._open_shape_modal(player)
        elif index == 3:
            self._open_clipboard_menu(player)
        elif index == 4:
            self._open_brush_modal(player)
        elif index == 5:
            self._open_history_menu(player)

    def _open_selection_menu(self, player: Any) -> None:
        form = ActionForm(
            title="§l§6Selection Menu",
            content="§7Choose a selection action:",
            on_submit=lambda p, idx: self._on_selection_choice(p, idx),
        )
        form.add_button("Give Selection Wand\n§8//wand")
        form.add_button("Set Pos1 Here\n§8//pos1")
        form.add_button("Set Pos2 Here\n§8//pos2")
        form.add_button("Toggle Outline Particles\n§8//drawsel")
        form.add_button("Expand Vert (Sky-to-Bedrock)\n§8//expand vert")
        form.add_button("Clear Selection\n§8//desel")
        player.send_form(form)

    def _on_selection_choice(self, player: Any, index: int) -> None:
        cmds = ["//wand", "//pos1", "//pos2", "//drawsel", "//expand vert", "//desel"]
        if 0 <= index < len(cmds):
            player.perform_command(cmds[index])

    def _open_region_modal(self, player: Any) -> None:
        form = ModalForm(
            title="§l§6Region Operations",
            controls=[
                TextInput("Pattern (for set / walls / replace target)", placeholder="stone", default_value="stone"),
                TextInput("Mask (optional source block for replace)", placeholder="dirt,grass_block", default_value=""),
                Toggle("Fill Walls Instead of Solid Fill", default_value=False),
            ],
            submit_button="Run Region Edit",
            on_submit=lambda p, raw: self._on_region_submit(p, raw),
        )
        player.send_form(form)

    def _on_region_submit(self, player: Any, raw_json: str) -> None:
        import json

        data = json.loads(raw_json)
        pattern = str(data[0] or "").strip()
        src_mask = str(data[1] or "").strip()
        walls_only = bool(data[2])
        if not pattern:
            return
        if src_mask:
            player.perform_command(f"//replace {src_mask} {pattern}")
        elif walls_only:
            player.perform_command(f"//walls {pattern}")
        else:
            player.perform_command(f"//set {pattern}")

    def _open_shape_modal(self, player: Any) -> None:
        from endstone.form import Dropdown

        form = ModalForm(
            title="§l§6Shape Generator",
            controls=[
                Dropdown("Shape Type", options=["sphere", "hsphere", "cyl", "hcyl", "pyramid", "cone"], default_index=0),
                TextInput("Pattern", placeholder="glass", default_value="stone"),
                Slider("Radius / Size", min=1.0, max=20.0, step=1.0, default_value=5.0),
                Slider("Height (cylinder/cone)", min=1.0, max=20.0, step=1.0, default_value=5.0),
            ],
            submit_button="Generate Shape",
            on_submit=lambda p, raw: self._on_shape_submit(p, raw),
        )
        player.send_form(form)

    def _on_shape_submit(self, player: Any, raw_json: str) -> None:
        import json

        data = json.loads(raw_json)
        shapes = ["sphere", "hsphere", "cyl", "hcyl", "pyramid", "cone"]
        shape = shapes[int(data[0])] if 0 <= int(data[0]) < len(shapes) else "sphere"
        pat = str(data[1] or "stone").strip()
        rad = int(data[2])
        h = int(data[3])
        if shape in ("cyl", "hcyl"):
            player.perform_command(f"//{shape} {pat} {rad} {h}")
        elif shape == "cone":
            player.perform_command(f"//cone {pat} {rad} {h}")
        else:
            player.perform_command(f"//{shape} {pat} {rad}")

    def _open_clipboard_menu(self, player: Any) -> None:
        form = ActionForm(
            title="§l§6Clipboard Menu",
            content="§7Select a clipboard operation:",
            on_submit=lambda p, idx: self._on_clipboard_choice(p, idx),
        )
        form.add_button("Copy Selection\n§8//copy")
        form.add_button("Cut Selection\n§8//cut")
        form.add_button("Paste at Player\n§8//paste")
        form.add_button("Paste Ignoring Air\n§8//paste -a")
        form.add_button("Rotate 90 Degrees Y\n§8//rotate 90")
        form.add_button("Flip Direction\n§8//flip")
        player.send_form(form)

    def _on_clipboard_choice(self, player: Any, index: int) -> None:
        cmds = ["//copy", "//cut", "//paste", "//paste -a", "//rotate 90", "//flip"]
        if 0 <= index < len(cmds):
            player.perform_command(cmds[index])

    def _open_brush_modal(self, player: Any) -> None:
        from endstone.form import Dropdown

        form = ModalForm(
            title="§l§6Brush Binding",
            controls=[
                Dropdown("Brush Kind (hold brush item in hand)", options=["sphere", "cylinder", "smooth", "splatter", "extinguish"], default_index=0),
                TextInput("Pattern", placeholder="stone", default_value="stone"),
                Slider("Brush Radius", min=1.0, max=12.0, step=1.0, default_value=4.0),
            ],
            submit_button="Bind Brush to Held Item",
            on_submit=lambda p, raw: self._on_brush_submit(p, raw),
        )
        player.send_form(form)

    def _on_brush_submit(self, player: Any, raw_json: str) -> None:
        import json

        data = json.loads(raw_json)
        kinds = ["sphere", "cylinder", "smooth", "splatter", "extinguish"]
        kind = kinds[int(data[0])] if 0 <= int(data[0]) < len(kinds) else "sphere"
        pat = str(data[1] or "stone").strip()
        rad = int(data[2])
        if kind in ("smooth", "extinguish"):
            player.perform_command(f"//br {kind} {rad}")
        else:
            player.perform_command(f"//br {kind} {pat} {rad}")

    def _open_history_menu(self, player: Any) -> None:
        form = ActionForm(
            title="§l§6History and Preferences",
            content="§7Quick undo/redo and session toggles:",
            on_submit=lambda p, idx: self._on_history_choice(p, idx),
        )
        form.add_button("Undo Last Edit\n§8//undo")
        form.add_button("Redo Last Undo\n§8//redo")
        form.add_button("Toggle Fast Mode\n§8//fast")
        form.add_button("Toggle Edit Wand\n§8//toggleeditwand")
        form.add_button("Toggle Super Pickaxe\n§8//")
        form.add_button("Clear Global Mask\n§8//gmask")
        player.send_form(form)

    def _on_history_choice(self, player: Any, index: int) -> None:
        cmds = ["//undo", "//redo", "//fast", "//toggleeditwand", "//", "//gmask"]
        if 0 <= index < len(cmds):
            player.perform_command(cmds[index])
