#!/usr/bin/env python3
"""Безопасные тесты поиска Настроек Kvorix: без кликов, сканирования сети и изменения настроек.

  python3 test_settings_search.py --source /usr/local/share/armbian-gui/center.py
  ... --gtk   # реальный GTK, только скрытое тестовое окно, заглушки страниц
"""
import argparse
import ast
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "/usr/local/share/armbian-gui")
from settings_search import SearchIndex, swap_layout, visible_labels, words  # noqa: E402


FIXTURE = '''
class Center:
    def page_sound(self):
        p = ui.Page("Звук", "Громкость и проверка звука")
        p.card("Выход звука", icon="secret-icon-name")
        p.add(ui.row("Проверить звук", sub="Проиграть стереосигнал"))
        C.run(["secret-command-do-not-index"])
        password = "secret-password-do-not-index"
        Gtk.Label(label=password)
        ui.entry(text="secret-default-do-not-index", hint="Имя устройства")
        return p
    def page_devices(self):
        return ui.Page("Устройства", "Флешки и принтеры")
    def page_timelang(self):
        return ui.Page("Время и язык", "Часовой пояс и раскладки клавиатуры")
    def page_network(self):
        return ui.Page("Сеть", "Подключения Wi-Fi")
'''
CLUSTER_FIXTURE = '''
def build_cluster_page(center):
    p = ui.Page("Кластер", "Распределённые вычисления")
    p.card("Охлаждение в одном корпусе", "Тепловой режим плат")
    p.add(ui.button("Зеркало бэкапов", run_cmd))
    return p
'''
MENU = [("sound", "Звук", ""), ("__sec__", "Устройства и сеть", ""),
        ("devices", "Устройства", ""), ("timelang", "Время и язык", ""),
        ("network", "Сеть и интернет", ""), ("appearance", "Персонализация", ""),
        ("cluster", "Кластер", "")]
SOURCE = None
GTK = False


def metadata(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("MENU", "KEYWORDS"):
                    values[target.id] = ast.literal_eval(node.value)
    return values["MENU"], values["KEYWORDS"]


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.index = SearchIndex(MENU, source=FIXTURE, extra_pages={"cluster": CLUSTER_FIXTURE})

    def first(self, query):
        results = self.index.search(query)
        self.assertTrue(results, query)
        return results[0].key

    def test_title(self):
        self.assertEqual(self.first("звук"), "sound")

    def test_content_not_in_title(self):
        self.assertEqual(self.first("стереосигнал"), "sound")
        self.assertEqual(self.first("проверить звук"), "sound")

    def test_extra_module_cluster_indexed(self):
        self.assertEqual(self.first("охлаждение в одном корпусе"), "cluster")
        self.assertEqual(self.first("зеркало бэкапов"), "cluster")

    def test_wrong_keyboard_layout_fallback(self):
        self.assertEqual(swap_layout("ghbynth"), "принтер")
        self.assertEqual(self.first("pder"), "sound")       # «звук» в EN-раскладке
        self.assertEqual(self.first("ghbynth"), "devices")  # «принтер» в EN-раскладке
        self.assertEqual(self.first("цшаш"), "network")     # «wifi» в RU-раскладке
        self.assertEqual(self.first("ntvysq"), "appearance")  # «темный» в EN-раскладке

    def test_normalization(self):
        self.assertEqual(words("ТЁМНАЯ"), words("тёмная"))
        self.assertEqual(words("ТЁМНАЯ"), words("темная"))
        self.assertEqual(self.first("ТЁМНЫЙ"), "appearance")

    def test_wifi_spellings(self):
        for query in ("Wi-Fi", "WI FI", "wi‑fi", "wifi", "вайфай"):
            with self.subTest(query=query):
                self.assertEqual(self.first(query), "network")

    def test_inflections(self):
        for query, expected in (("флешку", "devices"), ("принтера", "devices"),
                                ("громкости", "sound"), ("раскладки", "timelang")):
            with self.subTest(query=query):
                self.assertEqual(self.first(query), expected)

    def test_all_words_required(self):
        self.assertEqual(self.index.search("звук принтер"), [])

    def test_word_prefix(self):
        self.assertEqual(self.first("стерео"), "sound")

    def test_empty_and_unknown(self):
        for query in ("", "  ", "---", "несуществующийпараметр"):
            self.assertEqual(self.index.search(query), [])

    def test_no_section_results(self):
        self.assertNotIn("__sec__", self.index.documents)

    def test_secrets_and_commands_not_indexed(self):
        for query in ("secret", "command", "password", "default", "icon-name"):
            self.assertEqual(self.index.search(query), [], query)

    def test_malformed_source_falls_back(self):
        self.assertEqual(visible_labels("bad syntax : :"), {})
        self.assertEqual(SearchIndex(MENU, source="bad syntax : :").search("звук")[0].key, "sound")

    def test_missing_source_falls_back(self):
        index = SearchIndex.from_file(MENU, {}, "/path/that/does/not/exist")
        self.assertEqual(index.search("звук")[0].key, "sound")

    def test_title_ranks_before_other_content(self):
        source = 'class Center:\n def page_devices(self):\n  return ui.Page("Звук и принтер")\n'
        index = SearchIndex(MENU, source=source)
        self.assertEqual(index.search("звук")[0].key, "sound")

    def test_index_never_executes_source(self):
        source = 'raise RuntimeError("source executed")\n' + FIXTURE
        self.assertEqual(SearchIndex(MENU, source=source).search("стерео")[0].key, "sound")


@unittest.skipUnless(SOURCE, "--source не указан")
class InstalledSourceTests(unittest.TestCase):
    def setUp(self):
        menu, keywords = metadata(SOURCE)
        self.index = SearchIndex.from_file(menu, keywords, SOURCE)

    def test_every_page_in_menu_is_indexed(self):
        menu, _ = metadata(SOURCE)
        self.assertEqual(len(self.index.documents), len([1 for key, _, _ in menu if key != "__sec__"]))
        self.assertGreaterEqual(len(self.index.documents), 21)

    def test_real_queries_including_cluster_and_layouts(self):
        for query, expected in (("звук", "sound"), ("проверить звук", "sound"),
                                ("флешку", "devices"), ("извлечь флешку", "devices"),
                                ("раскладка", "timelang"), ("часовой пояс", "timelang"),
                                ("wi-fi", "network"), ("тёмный", "appearance"),
                                ("ночной свет", "appearance"), ("свободное место", "disks"),
                                ("разрешение экрана", "display"), ("естественная прокрутка", "devices"),
                                ("подкачка", "perf"), ("сбалансированный", "perf"),
                                ("обход блокировок", "services"), ("часы на корпусе", "services"),
                                ("секретным ключом", "security"), ("охлаждение", "cluster"),
                                ("зеркало бэкапов", "cluster"), ("ghbynth", "devices"),
                                ("цшаш", "network"), ("обои", "wallpaper"),
                                ("обновления", "updates"), ("нейросеть", "ai")):
            with self.subTest(query=query):
                hits = self.index.search(query)
                self.assertTrue(hits, query)
                self.assertEqual(hits[0].key, expected)

    def test_bounded_search_latency(self):
        start = time.monotonic()
        for _ in range(20):
            for query in ("звук", "ночной свет", "флешка", "раскладка", "wi-fi", "ghbynth"):
                self.index.search(query)
        elapsed = time.monotonic() - start
        print("SEARCH_BENCH: %.2f ms/query (120 queries)" % (elapsed * 1000 / 120))
        self.assertLess(elapsed, 10, "Поиск дольше допустимого лимита")


@unittest.skipUnless(GTK and SOURCE, "--gtk и --source не указаны")
class GtkTests(unittest.TestCase):
    def setUp(self):
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk
        self.Gtk, self.Gdk = Gtk, Gdk
        sys.path.insert(0, str(Path(SOURCE).parent))
        import center
        self.center = center
        # Ни один настоящий builder не вызывается, окно НЕ показывается на ТВ.
        self.opens = []
        self.patches = []
        for name in dir(center.Center):
            if name.startswith("page_"):
                key = name[5:]
                def fake(owner, key=key):
                    self.opens.append(key)
                    return Gtk.Box()
                item = patch.object(center.Center, name, fake)
                item.start()
                self.patches.append(item)
        self.command_patch = patch.object(center.C, "run", side_effect=AssertionError("Unexpected system command"))
        self.command_patch.start()
        self.w = center.Center()
        self.s = self.w.settings_search
        self.opens.clear()

    def tearDown(self):
        if hasattr(self, "w"):
            self.w.destroy()
        self.command_patch.stop()
        for item in self.patches:
            item.stop()
        while self.Gtk.events_pending():
            self.Gtk.main_iteration_do(False)

    def query(self, text):
        self.w.search.set_text(text)
        self.s._changed(self.w.search)

    def test_typing_does_not_build_pages_and_shows_hint(self):
        for text in ("w", "wi", "wifi", "флешка", "естественная прокрутка"):
            self.query(text)
        self.assertIn("→", self.s.status_label.get_text())
        self.assertEqual(self.opens, [])
        self.assertEqual(self.w.stack.get_visible_child_name(), "overview")
        self.assertFalse(self.w.get_visible())

    def test_enter_opens_correct_page_immediately(self):
        self.w.search.set_text("раскладка")
        self.s._activate(self.w.search)
        self.assertEqual(self.opens, ["timelang"])
        self.assertEqual(self.w.stack.get_visible_child_name(), "timelang")

    def test_unknown_query_shows_message_and_keeps_page(self):
        self.query("абракадабра987654")
        self.assertIn("Ничего не найдено", self.s.status_label.get_text())
        self.s._activate(self.w.search)
        self.assertEqual(self.opens, [])
        self.assertEqual(self.w.stack.get_visible_child_name(), "overview")

    def test_escape_restores_full_menu(self):
        self.query("звук")
        self.s._key(self.w.search, type("Event", (), {"keyval": self.Gdk.KEY_Escape})())
        self.assertEqual(self.w.search.get_text(), "")
        for row in self.w.rows.values():
            self.assertTrue(self.s._filter(row))
        self.assertEqual(self.opens, [])

    def test_arrow_keys_do_not_build_pages(self):
        self.query("память")
        self.s._key(self.w.search, type("Event", (), {"keyval": self.Gdk.KEY_Down})())
        self.assertEqual(self.opens, [])
        expected = self.s.hits[self.s.cursor].key
        self.s._activate(self.w.search)
        self.assertEqual(self.w.stack.get_visible_child_name(), expected)

    def test_typing_does_not_steal_selected_page(self):
        self.w.open_page("sound")
        self.opens.clear()
        self.query("wifi")
        self.assertEqual(self.opens, [])
        self.assertEqual(self.w.stack.get_visible_child_name(), "sound")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source")
    parser.add_argument("--gtk", action="store_true")
    args, rest = parser.parse_known_args()
    SOURCE, GTK = args.source, args.gtk
    InstalledSourceTests.__unittest_skip__ = not bool(SOURCE)
    GtkTests.__unittest_skip__ = not (GTK and SOURCE)
    unittest.main(argv=[sys.argv[0]] + rest)
