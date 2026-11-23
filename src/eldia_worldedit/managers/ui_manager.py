"""Interactive Bedrock Form UI menus for WorldEdit (/ewe gui)."""

from __future__ import annotations

import json
from typing import Any

from endstone.form import ActionForm, Dropdown, ModalForm, Slider, TextInput, Toggle

from .lang_manager import LangManager


class UIManager:
    """Builds and opens localized Bedrock ActionForm / ModalForm workflows."""

    def open_main_menu(self, player: Any, session_summary: str, lang: LangManager | None = None) -> None:
        lm = lang or LangManager("en")
        form = ActionForm(
            title=f"§l§6{lm.t('ui.title')}",
            content=f"§7{session_summary}",
            on_submit=lambda p, idx: self._on_main_choice(p, idx, lm),
        )
        form.add_button(lm.t("ui.btn_sel"))
        form.add_button(lm.t("ui.btn_region"))
        form.add_button(lm.t("ui.btn_shape"))
        form.add_button(lm.t("ui.btn_clip"))
        form.add_button(lm.t("ui.btn_brush"))
        form.add_button(lm.t("ui.btn_hist"))
        player.send_form(form)

    def _on_main_choice(self, player: Any, index: int, lang: LangManager) -> None:
        if index == 0:
            self._open_selection_menu(player, lang)
        elif index == 1:
            self._open_region_modal(player, lang)
        elif index == 2:
            self._open_shape_modal(player, lang)
        elif index == 3:
            self._open_clipboard_menu(player, lang)
        elif index == 4:
            self._open_brush_modal(player, lang)
        elif index == 5:
            self._open_history_menu(player, lang)

    def _open_selection_menu(self, player: Any, lang: LangManager) -> None:
        is_th = lang.language == "th"
        form = ActionForm(
            title="§l§6เมนูเลือกพื้นที่" if is_th else "§l§6Selection Menu",
            content="§7เลือกคำสั่งที่ต้องการ:" if is_th else "§7Choose a selection action:",
            on_submit=lambda p, idx: self._on_selection_choice(p, idx),
        )
        if is_th:
            form.add_button("รับไม้คทาเลือกพื้นที่\n§8//wand")
            form.add_button("ตั้งจุดที่ 1 ณ จุดยืน\n§8//pos1")
            form.add_button("ตั้งจุดที่ 2 ณ จุดยืน\n§8//pos2")
            form.add_button("เปิด/ปิดเส้นขอบพาร์ติเคิล\n§8//drawsel")
            form.add_button("ขยายพื้นที่แนวตั้งทั้งหมด\n§8//expand vert")
            form.add_button("ล้างพื้นที่ที่เลือก\n§8//desel")
        else:
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

    def _open_region_modal(self, player: Any, lang: LangManager) -> None:
        is_th = lang.language == "th"
        form = ModalForm(
            title="§l§6แก้ไขพื้นที่" if is_th else "§l§6Region Operations",
            controls=[
                TextInput("แพตเทิร์นบล็อก (Pattern)" if is_th else "Pattern (set / walls / target)", placeholder="stone", default_value="stone"),
                TextInput("เงื่อนไขบล็อกเดิม (เว้นว่างถ้าแทนทั้งหมด)" if is_th else "Mask (optional source block)", placeholder="dirt,grass_block", default_value=""),
                Toggle("สร้างเฉพาะกำแพง (Walls)" if is_th else "Fill Walls Only", default_value=False),
            ],
            submit_button="ยืนยันการแก้ไข" if is_th else "Run Region Edit",
            on_submit=lambda p, raw: self._on_region_submit(p, raw),
        )
        player.send_form(form)

    def _on_region_submit(self, player: Any, raw_json: str) -> None:
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

    def _open_shape_modal(self, player: Any, lang: LangManager) -> None:
        is_th = lang.language == "th"
        form = ModalForm(
            title="§l§6สร้างรูปทรง 3 มิติ" if is_th else "§l§6Shape Generator",
            controls=[
                Dropdown("รูปทรง" if is_th else "Shape Type", options=["sphere", "hsphere", "cyl", "hcyl", "pyramid", "cone"], default_index=0),
                TextInput("บล็อก / Pattern" if is_th else "Pattern", placeholder="glass", default_value="stone"),
                Slider("รัศมี / ขนาด" if is_th else "Radius / Size", min=1.0, max=20.0, step=1.0, default_value=5.0),
                Slider("ความสูง (ทรงกระบอก/กรวย)" if is_th else "Height (cyl/cone)", min=1.0, max=20.0, step=1.0, default_value=5.0),
            ],
            submit_button="สร้างรูปทรง" if is_th else "Generate Shape",
            on_submit=lambda p, raw: self._on_shape_submit(p, raw),
        )
        player.send_form(form)

    def _on_shape_submit(self, player: Any, raw_json: str) -> None:
        data = json.loads(raw_json)
        shapes = ["sphere", "hsphere", "cyl", "hcyl", "pyramid", "cone"]
        shape = shapes[int(data[0])] if 0 <= int(data[0]) < len(shapes) else "sphere"
        pat = str(data[1] or "stone").strip()
        rad = int(data[2])
        h = int(data[3])
        if shape in ("cyl", "hcyl", "cone"):
            player.perform_command(f"//{shape} {pat} {rad} {h}")
        else:
            player.perform_command(f"//{shape} {pat} {rad}")

    def _open_clipboard_menu(self, player: Any, lang: LangManager) -> None:
        is_th = lang.language == "th"
        form = ActionForm(
            title="§l§6เมนู Clipboard" if is_th else "§l§6Clipboard Menu",
            content="§7เลือกการทำงาน:" if is_th else "§7Select a clipboard operation:",
            on_submit=lambda p, idx: self._on_clipboard_choice(p, idx),
        )
        if is_th:
            form.add_button("คัดลอกพื้นที่\n§8//copy")
            form.add_button("ตัดพื้นที่\n§8//cut")
            form.add_button("วางทั้งหมด\n§8//paste")
            form.add_button("วางไม่ทับอากาศ\n§8//paste -a")
            form.add_button("หมุน 90 องศา\n§8//rotate 90")
            form.add_button("กลับด้านตามมุมมอง\n§8//flip")
        else:
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

    def _open_brush_modal(self, player: Any, lang: LangManager) -> None:
        is_th = lang.language == "th"
        form = ModalForm(
            title="§l§6ตั้งค่าแปรง" if is_th else "§l§6Brush Binding",
            controls=[
                Dropdown("ชนิดแปรง (ถือไอเทมไว้ในมือ)" if is_th else "Brush Kind (hold item)", options=["sphere", "cylinder", "smooth", "splatter", "extinguish"], default_index=0),
                TextInput("บล็อก / Pattern" if is_th else "Pattern", placeholder="stone", default_value="stone"),
                Slider("รัศมีแปรง" if is_th else "Brush Radius", min=1.0, max=12.0, step=1.0, default_value=4.0),
            ],
            submit_button="ผูกแปรงกับไอเทม" if is_th else "Bind Brush",
            on_submit=lambda p, raw: self._on_brush_submit(p, raw),
        )
        player.send_form(form)

    def _on_brush_submit(self, player: Any, raw_json: str) -> None:
        data = json.loads(raw_json)
        kinds = ["sphere", "cylinder", "smooth", "splatter", "extinguish"]
        kind = kinds[int(data[0])] if 0 <= int(data[0]) < len(kinds) else "sphere"
        pat = str(data[1] or "stone").strip()
        rad = int(data[2])
        if kind in ("smooth", "extinguish"):
            player.perform_command(f"//br {kind} {rad}")
        else:
            player.perform_command(f"//br {kind} {pat} {rad}")

    def _open_history_menu(self, player: Any, lang: LangManager) -> None:
        is_th = lang.language == "th"
        form = ActionForm(
            title="§l§6ประวัติและการตั้งค่า" if is_th else "§l§6History and Preferences",
            content="§7คำสั่งด่วน:" if is_th else "§7Quick toggles:",
            on_submit=lambda p, idx: self._on_history_choice(p, idx),
        )
        if is_th:
            form.add_button("ย้อนกลับล่าสุด\n§8//undo")
            form.add_button("ทำซ้ำล่าสุด\n§8//redo")
            form.add_button("สลับ Fast Mode\n§8//fast")
            form.add_button("สลับไม้คทา\n§8//toggleeditwand")
            form.add_button("สลับ Super Pickaxe\n§8//")
            form.add_button("สลับภาษา EN / TH\n§8/ewe lang")
        else:
            form.add_button("Undo Last Edit\n§8//undo")
            form.add_button("Redo Last Undo\n§8//redo")
            form.add_button("Toggle Fast Mode\n§8//fast")
            form.add_button("Toggle Edit Wand\n§8//toggleeditwand")
            form.add_button("Toggle Super Pickaxe\n§8//")
            form.add_button("Switch to Thai Language\n§8/ewe lang th")
        player.send_form(form)

    def _on_history_choice(self, player: Any, index: int) -> None:
        cmds = ["//undo", "//redo", "//fast", "//toggleeditwand", "//", "/ewe lang th"]
        if 0 <= index < len(cmds):
            player.perform_command(cmds[index])
