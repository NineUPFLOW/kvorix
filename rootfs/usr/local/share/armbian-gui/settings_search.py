
import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import unicodedata


EXTRA_WORDS = {
    "overview": "главная обзор сводка начало быстрый доступ плитки",
    "bluetooth": "блютуз блютус наушники колонка гарнитура сопряжение",
    "devices": "флешка флэшка USB накопитель печать принтер сканер мышь пульт датчик указатель прокрутка телефон экран камера",
    "disks": "свободное место накопитель раздел диск хранилище память очистка",
    "display": "изображение масштаб границы калибровка телевизор частота герц экран монитор",
    "sound": "звук наушники колонки микшер стерео громкость тишина беззвучный",
    "timelang": "раскладка клавиатура русский английский часы дата время пояс синхронизация",
    "network": "wifi wi-fi вайфай провод ethernet кабель шлюз адрес подключение роутер интернет",
    "appearance": "темная темный светлая светлый оформление шрифт буквы ночной свет прозрачность акцент",
    "wallpaper": "обои заставка фото картинка фон рабочего стола",
    "power": "сон выключение перезагрузка блокировка гашение простой питание энергосбережение",
    "autostart": "автозапуск вход запуск программ старт сеанс",
    "packages": "удалить установленные установка программа приложение магазин софт",
    "users": "пользователь учетная запись аккаунт вход автологин администратор профиль",
    "updates": "обновления проверить установить апгрейд пакеты свежие версии",
    "security": "безопасность защита брандмауэр межсетевой порт журнал ошибок права секретный ключ защита экрана funnel vnc ssh автообновления",
    "ai": "ии нейросеть агент помощник слот история сессия удаленный",
    "perf": "быстродействие нагрузка температура нагрев частота ядра кэш озу подкачка монитор ресурсов сбалансированный экономия энергии максимальная скорость",
    "services": "службы фоновые процессы демоны запуск остановка состояние обход блокировок zapret запрет tailscale часы на корпусе печать показ экрана",
    "system": "система имя компьютера устройство версия ядро модель железо процессор",
}

_RU_SUFFIXES = tuple(sorted(("иями", "ями", "ами", "ого", "ему", "ому", "ыми", "ими",
                             "ия", "ие", "ию", "ая", "яя", "ую", "юю", "ое", "ее", "ые",
                             "ий", "ый", "ой", "ей", "ом", "ем", "ым", "им", "ах", "ях",
                             "ам", "ям", "ов", "ев", "ы", "и", "а", "я", "у", "ю", "е", "о", "ь"),
                            key=len, reverse=True))

_EN_KEYS = "qwertyuiop[]asdfghjkl;'zxcvbnm,./`"
_RU_KEYS = "йцукенгшщзхъфывапролджэячсмитьбю.ё"
_SWAP_MAP = str.maketrans(
    _EN_KEYS + _EN_KEYS.upper() + _RU_KEYS + _RU_KEYS.upper(),
    _RU_KEYS + _RU_KEYS.upper() + _EN_KEYS + _EN_KEYS.upper(),
)


def swap_layout(text):
    
    return text.translate(_SWAP_MAP)


@lru_cache(maxsize=1024)
def words(text):
    
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    text = re.sub(r"\bwi[\s_\-\u2010-\u2015]*fi\b", "wifi", text)
    return tuple(dict.fromkeys(re.findall(r"[^\W_]+", text, flags=re.UNICODE)))


@lru_cache(maxsize=2048)
def _stem(word):
    if re.fullmatch("[а-я]+", word):
        for ending in _RU_SUFFIXES:
            if word.endswith(ending) and len(word) - len(ending) >= 3:
                return word[:-len(ending)]
    return word


def _literal_strings(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [s for item in node.elts for s in _literal_strings(item)]
    return []


def _extract_ui_labels(ast_root):
    
    two_args = {"ui.Page", "ui.Card", "ui.header", "ui.info_row"}
    first_arg = {"ui._lbl", "ui.row", "ui.button", "ui.combo"}
    gtk_labels = {"Gtk.Label", "Gtk.Button", "Gtk.CheckButton", "Gtk.Expander"}
    labels = []
    for call in ast.walk(ast_root):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if not isinstance(func, ast.Attribute):
            continue
        name = (func.value.id + "." + func.attr) if isinstance(func.value, ast.Name) else ""
        if func.attr == "card" or name in two_args:
            for value in call.args[:2]:
                labels.extend(_literal_strings(value))
            accepted = {"title", "subtitle"}
        elif name in first_arg:
            if call.args:
                labels.extend(_literal_strings(call.args[0]))
            accepted = {"label", "sub"}
        elif name in gtk_labels:
            accepted = {"label"}
        elif name == "ui.entry":
            accepted = {"hint"}
        else:
            continue
        for kw in call.keywords:
            if kw.arg in accepted:
                labels.extend(_literal_strings(kw.value))
    return tuple(dict.fromkeys(s for s in labels if s.strip()))


def visible_labels(source, extra_pages=None):
    
    result = {}
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, TypeError):
        tree = None
    if tree is not None:
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef) or cls.name != "Center":
                continue
            for method in cls.body:
                if not isinstance(method, ast.FunctionDef) or not method.name.startswith("page_"):
                    continue
                result[method.name[5:]] = _extract_ui_labels(method)
    for page_key, mod_source in (extra_pages or {}).items():
        try:
            mod_tree = ast.parse(mod_source)
        except (SyntaxError, ValueError, TypeError):
            continue
        merged = list(result.get(page_key, ()))
        for fn in mod_tree.body:
            if isinstance(fn, (ast.FunctionDef, ast.ClassDef)):
                merged.extend(_extract_ui_labels(fn))
        result[page_key] = tuple(dict.fromkeys(s for s in merged if s.strip()))
    return result


@dataclass(frozen=True)
class SearchHit:
    key: str
    title: str
    score: int
    hint: str = ""


class SearchIndex:
    
    def __init__(self, menu, keywords=None, source="", extra_pages=None):
        labels = visible_labels(source, extra_pages=extra_pages)
        keywords = keywords or {}
        self.documents = {}
        for key, title, _icon in menu:
            if key == "__sec__":
                continue
            self.documents[key] = {
                "title": title,
                "title_words": words(title),
                "keywords": words(keywords.get(key, "") + " " + EXTRA_WORDS.get(key, "")),
                "labels": labels.get(key, ()),
                "content": words(" ".join(labels.get(key, ()))),
            }

    @classmethod
    def from_file(cls, menu, keywords, filename):
        p = Path(filename)
        try:
            source = p.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            source = ""
        extra = {}
        cluster_file = p.with_name("cluster_page.py")
        try:
            if cluster_file.is_file():
                extra["cluster"] = cluster_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            pass
        return cls(menu, keywords, source, extra_pages=extra)

    @staticmethod
    def _quality(term, candidates):
        if term in candidates:
            return 3
        if len(term) < 3:
            return 0
        stem = _stem(term)
        if any(stem == _stem(word) for word in candidates):
            return 2
        if any(word.startswith(term) or _stem(word).startswith(stem) for word in candidates):
            return 1
        return 0

    def _search_terms(self, terms):
        if not terms:
            return []
        hits = []
        for key, doc in self.documents.items():
            score = 0
            for term in terms:
                quality = max(self._quality(term, doc["title_words"]) * 40,
                              self._quality(term, doc["keywords"]) * 18,
                              self._quality(term, doc["content"]) * 8)
                if not quality:
                    break
                score += quality
            else:
                if terms == doc["title_words"]:
                    score += 200
                hint = next((label for label in doc["labels"]
                             if any(self._quality(term, words(label)) for term in terms)), "")
                hits.append(SearchHit(key, doc["title"], score, hint))
        return sorted(hits, key=lambda hit: -hit.score)

    def search(self, query):
        raw = query[:200]
        terms = words(raw)
        if not terms:
            return []
        hits = self._search_terms(terms)
        if hits:
            return hits
        alt_terms = words(swap_layout(raw))
        if alt_terms and alt_terms != terms:
            return self._search_terms(alt_terms)
        return []


class SettingsSearch:
    
    def __init__(self, owner, entry, nav, menu, keywords, filename):
        from gi.repository import Gdk, Gtk
        self.Gdk, self.Gtk = Gdk, Gtk
        self.owner, self.entry, self.nav = owner, entry, nav
        self._filename = filename
        self._menu = menu
        self._keywords = keywords
        self._mtimes = self._stat_mtimes()
        self.index = SearchIndex.from_file(menu, keywords, filename)
        entry.set_max_length(200)
        self.query, self.hits, self.cursor = "", [], 0
        self.original_order = {row: i for i, row in enumerate(nav.get_children())}
        self.ranks = {}
        self._marked = None
        self.popover = None

        self.status = Gtk.ListBoxRow()
        self.status.key = None
        self.status.set_selectable(False)
        self.status.set_activatable(False)
        label = Gtk.Label(label="Введите название или слово из параметра.", xalign=0)
        label.set_line_wrap(True)
        label.set_max_width_chars(28)
        label.set_margin_start(12)
        label.set_margin_end(12)
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        label.get_style_context().add_class("muted")
        self.status.add(label)
        self.status_label = label
        nav.add(self.status)
        self.status.show_all()
        nav.set_filter_func(self._filter)
        nav.set_sort_func(self._sort)

        css = Gtk.CssProvider()
        css.load_from_data(b"row.search-candidate { background-color: rgba(90, 155, 255, 0.18); border-radius: 6px; }")
        Gtk.StyleContext.add_provider_for_screen(owner.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._css = css
        self._connections = [
            (entry, entry.connect("search-changed", self._changed)),
            (entry, entry.connect("activate", self._activate)),
            (entry, entry.connect("stop-search", self._clear)),
            (entry, entry.connect("key-press-event", self._key)),
            (owner, owner.connect("key-press-event", self._window_key)),
            (owner, owner.connect("size-allocate", self._size)),
        ]
        entry.set_tooltip_text("Поиск по названиям и содержимому · Ctrl+F\n↑/↓ — выбрать, Enter — открыть, Esc — очистить")
        self.search_button = Gtk.Button.new_from_icon_name("system-search", Gtk.IconSize.BUTTON)
        self.search_button.set_tooltip_text("Найти параметр (Ctrl+F)")
        self.search_button.set_no_show_all(True)
        self.search_button.connect("clicked", lambda *_: self.focus())
        owner.get_titlebar().pack_end(self.search_button)
        owner.connect("destroy", self._destroy)

    def _stat_mtimes(self):
        p = Path(self._filename)
        out = []
        for f in (p, p.with_name("cluster_page.py")):
            try:
                out.append(f.stat().st_mtime_ns)
            except OSError:
                out.append(0)
        return tuple(out)

    def _maybe_reload_index(self):
        cur = self._stat_mtimes()
        if cur != self._mtimes:
            self._mtimes = cur
            self.index = SearchIndex.from_file(self._menu, self._keywords, self._filename)

    def _update_status_text(self, raw):
        if not words(raw):
            self.status_label.set_text("Введите название или слово из параметра.")
            return
        if not self.hits:
            self.status_label.set_text("Ничего не найдено.\nПопробуйте другое слово.")
            return
        cur = self.hits[self.cursor]
        base = "Найдено разделов: %d" % len(self.hits)
        if cur.hint and cur.hint.strip().casefold() != cur.title.strip().casefold():
            hint_short = cur.hint.strip().splitlines()[0]
            if len(hint_short) > 54:
                hint_short = hint_short[:51] + "…"
            self.status_label.set_text("%s\n→ %s" % (base, hint_short))
        else:
            self.status_label.set_text(base)

    def _filter(self, row):
        if row is self.status:
            return bool(words(self.query)) and not getattr(self, "_was_compact", False)
        if not words(self.query):
            return True
        return getattr(row, "key", None) in self.ranks

    def _sort(self, left, right):
        def order(row):
            if words(self.query):
                return (-1 if row is self.status else self.ranks.get(getattr(row, "key", None), 999), 0)
            return (self.original_order.get(row, 999), 0)
        a, b = order(left), order(right)
        return (a > b) - (a < b)

    def _mark(self):
        if self._marked is not None:
            self._marked.get_style_context().remove_class("search-candidate")
        self._marked = None
        if self.hits:
            row = self.owner.rows[self.hits[self.cursor].key]
            row.get_style_context().add_class("search-candidate")
            self._marked = row

    def _changed(self, entry):
        raw = entry.get_text()
        if raw == self.query:
            return
        self._maybe_reload_index()
        self.query = raw
        self.hits = self.index.search(raw)
        self.cursor = 0
        self.ranks = {hit.key: i for i, hit in enumerate(self.hits)}
        self.nav.unselect_all()
        self._update_status_text(raw)
        for key, row in self.owner.rows.items():
            hit = next((h for h in self.hits if h.key == key), None)
            row.set_tooltip_text(hit.hint if hit and hit.hint else self.index.documents[key]["title"])
        self.nav.invalidate_filter()
        self.nav.invalidate_sort()
        self._mark()
        if not words(raw):
            current = self.owner.stack.get_visible_child_name()
            if current in self.owner.rows:
                self.nav.select_row(self.owner.rows[current])

    def _activate(self, entry):
        self._changed(entry)
        if not self.hits:
            return
        selected = self.nav.get_selected_row()
        key = getattr(selected, "key", None)
        if key not in self.ranks:
            key = self.hits[self.cursor].key
        self.owner.open_page(key)
        if self.popover:
            self.popover.popdown()

    def _clear(self, *_args):
        self.entry.set_text("")
        self._changed(self.entry)

    def _key(self, entry, event):
        if event.keyval == self.Gdk.KEY_Escape:
            self._clear()
            return True
        if event.keyval not in (self.Gdk.KEY_Down, self.Gdk.KEY_Up):
            return False
        self._changed(entry)
        if not self.hits:
            return False
        step = 1 if event.keyval == self.Gdk.KEY_Down else -1
        self.cursor = max(0, min(len(self.hits) - 1, self.cursor + step))
        self.nav.unselect_all()
        self._mark()
        self._update_status_text(self.query)
        row = self._marked
        parent = self.nav.get_parent()
        while parent and not isinstance(parent, self.Gtk.ScrolledWindow):
            parent = parent.get_parent()
        if parent:
            adj, alloc = parent.get_vadjustment(), row.get_allocation()
            if alloc.y < adj.get_value():
                adj.set_value(alloc.y)
            elif alloc.y + alloc.height > adj.get_value() + adj.get_page_size():
                adj.set_value(alloc.y + alloc.height - adj.get_page_size())
        return True

    def _window_key(self, _owner, event):
        if event.state & self.Gdk.ModifierType.CONTROL_MASK and event.keyval in (self.Gdk.KEY_f, self.Gdk.KEY_F):
            self.focus()
            return True
        return False

    def focus(self):
        if self.entry.get_visible():
            entry = self.entry
        else:
            if self.popover is None:
                self.popover = self.Gtk.Popover.new(self.search_button)
                entry = self.Gtk.SearchEntry()
                entry.set_buffer(self.entry.get_buffer())
                entry.set_placeholder_text("Найти параметр")
                entry.set_size_request(280, -1)
                entry.set_margin_start(12)
                entry.set_margin_end(12)
                entry.set_margin_top(12)
                entry.set_margin_bottom(12)
                entry.connect("activate", self._activate)
                entry.connect("key-press-event", self._key)
                entry.connect("stop-search", self._clear)
                box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=4)
                box.pack_start(entry, False, False, 0)
                status = self.Gtk.Label(xalign=0)
                status.set_line_wrap(True)
                status.set_margin_start(12)
                status.set_margin_end(12)
                status.set_margin_bottom(12)
                status.get_style_context().add_class("muted")
                self.status_label.bind_property("label", status, "label", 2)
                box.pack_start(status, False, False, 0)
                self.popover.add(box)
                self._popover_entry = entry
            else:
                entry = self._popover_entry
            self.popover.show_all()
            self.popover.popup()
        entry.grab_focus()
        entry.select_region(0, -1)

    def _size(self, _owner, alloc):
        compact = alloc.width < 900
        self.search_button.set_visible(compact)
        if getattr(self, "_was_compact", None) != compact:
            self._was_compact = compact
            self.nav.invalidate_filter()

    def _destroy(self, *_args):
        self.Gtk.StyleContext.remove_provider_for_screen(self.owner.get_screen(), self._css)
        if self.popover:
            self.popover.destroy()


def attach(owner, entry, nav, menu, keywords, filename):
    return SettingsSearch(owner, entry, nav, menu, keywords, filename)
