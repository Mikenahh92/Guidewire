"""Tests for the cross-platform mapping tables."""

from guidewire.models.mappings import (
    ACTION_MAP,
    ROLE_MAP,
    STATE_MAP,
    resolve_action,
    resolve_role,
    resolve_state,
)

# ---------------------------------------------------------------------------
# Windows UIA role mappings
# ---------------------------------------------------------------------------


class TestWindowsRoles:
    """Windows UIA ControlType → normalized role."""

    def test_button(self) -> None:
        assert ROLE_MAP[("windows", "Button")] == "button"
        assert ROLE_MAP[("windows", "ControlType.Button")] == "button"

    def test_edit(self) -> None:
        assert ROLE_MAP[("windows", "Edit")] == "text_input"
        assert ROLE_MAP[("windows", "ControlType.Edit")] == "text_input"

    def test_checkbox(self) -> None:
        assert ROLE_MAP[("windows", "CheckBox")] == "checkbox"
        assert ROLE_MAP[("windows", "ControlType.CheckBox")] == "checkbox"

    def test_window(self) -> None:
        assert ROLE_MAP[("windows", "Window")] == "window"
        assert ROLE_MAP[("windows", "ControlType.Window")] == "window"

    def test_menu_item(self) -> None:
        assert ROLE_MAP[("windows", "MenuItem")] == "menu_item"

    def test_document(self) -> None:
        assert ROLE_MAP[("windows", "Document")] == "document"

    def test_list(self) -> None:
        assert ROLE_MAP[("windows", "List")] == "list"
        assert ROLE_MAP[("windows", "ListItem")] == "list_item"

    def test_tree(self) -> None:
        assert ROLE_MAP[("windows", "Tree")] == "tree"
        assert ROLE_MAP[("windows", "TreeItem")] == "tree_item"

    def test_tab(self) -> None:
        assert ROLE_MAP[("windows", "Tab")] == "tab"
        assert ROLE_MAP[("windows", "TabItem")] == "tab_item"

    def test_slider(self) -> None:
        assert ROLE_MAP[("windows", "Slider")] == "slider"

    def test_progress_bar(self) -> None:
        assert ROLE_MAP[("windows", "ProgressBar")] == "progress_bar"

    def test_hyperlink(self) -> None:
        assert ROLE_MAP[("windows", "Hyperlink")] == "link"

    def test_image(self) -> None:
        assert ROLE_MAP[("windows", "Image")] == "image"

    def test_custom(self) -> None:
        assert ROLE_MAP[("windows", "Custom")] == "custom"


# ---------------------------------------------------------------------------
# Linux AT-SPI role mappings
# ---------------------------------------------------------------------------


class TestLinuxRoles:
    """Linux AT-SPI role → normalized role."""

    def test_button(self) -> None:
        assert ROLE_MAP[("linux", "push button")] == "button"

    def test_checkbox(self) -> None:
        assert ROLE_MAP[("linux", "check box")] == "checkbox"

    def test_entry(self) -> None:
        assert ROLE_MAP[("linux", "entry")] == "text_input"
        assert ROLE_MAP[("linux", "editable text")] == "text_input"
        assert ROLE_MAP[("linux", "password text")] == "text_input"

    def test_radio_button(self) -> None:
        assert ROLE_MAP[("linux", "radio button")] == "radio_button"

    def test_window(self) -> None:
        assert ROLE_MAP[("linux", "window")] == "window"
        assert ROLE_MAP[("linux", "dialog")] == "dialog"

    def test_menu(self) -> None:
        assert ROLE_MAP[("linux", "menu bar")] == "menu_bar"
        assert ROLE_MAP[("linux", "menu item")] == "menu_item"

    def test_list(self) -> None:
        assert ROLE_MAP[("linux", "list")] == "list"
        assert ROLE_MAP[("linux", "list item")] == "list_item"

    def test_tree(self) -> None:
        assert ROLE_MAP[("linux", "tree")] == "tree"
        assert ROLE_MAP[("linux", "tree item")] == "tree_item"

    def test_table(self) -> None:
        assert ROLE_MAP[("linux", "table")] == "table"

    def test_tab(self) -> None:
        assert ROLE_MAP[("linux", "page tab")] == "tab_item"
        assert ROLE_MAP[("linux", "page tab list")] == "tab"

    def test_link(self) -> None:
        assert ROLE_MAP[("linux", "link")] == "link"

    def test_image(self) -> None:
        assert ROLE_MAP[("linux", "image")] == "image"

    def test_unknown(self) -> None:
        assert ROLE_MAP[("linux", "unknown")] == "custom"


# ---------------------------------------------------------------------------
# macOS mappings are out of scope
# ---------------------------------------------------------------------------


class TestNoMacOSMappings:
    """macOS mappings are not in scope for this epic."""

    def test_no_macos_roles(self) -> None:
        assert ("macos", "AXButton") not in ROLE_MAP

    def test_no_macos_states(self) -> None:
        assert ("macos", "AXEnabled") not in STATE_MAP

    def test_no_macos_actions(self) -> None:
        assert ("macos", "AXPress") not in ACTION_MAP


# ---------------------------------------------------------------------------
# Windows UIA state mappings
# ---------------------------------------------------------------------------


class TestWindowsStates:
    """Windows UIA properties → ElementStates fields."""

    def test_is_enabled(self) -> None:
        field, value = STATE_MAP[("windows", "IsEnabled")]
        assert field == "enabled"
        assert value(True) is True
        assert value(False) is False

    def test_has_keyboard_focus(self) -> None:
        field, _ = STATE_MAP[("windows", "HasKeyboardFocus")]
        assert field == "focused"

    def test_is_selected(self) -> None:
        field, _ = STATE_MAP[("windows", "IsSelected")]
        assert field == "selected"

    def test_toggle_state(self) -> None:
        field, transform = STATE_MAP[("windows", "ToggleState")]
        assert field == "checked"
        assert transform(0) is False
        assert transform(1) is True
        assert transform(2) == "mixed"

    def test_is_expanded(self) -> None:
        field, _ = STATE_MAP[("windows", "IsExpanded")]
        assert field == "expanded"

    def test_is_offscreen(self) -> None:
        field, _ = STATE_MAP[("windows", "IsOffscreen")]
        assert field == "offscreen"

    def test_is_read_only(self) -> None:
        field, _ = STATE_MAP[("windows", "IsReadOnly")]
        assert field == "read_only"

    def test_is_required(self) -> None:
        field, _ = STATE_MAP[("windows", "IsRequiredForForm")]
        assert field == "required"

    def test_visibility(self) -> None:
        field, transform = STATE_MAP[("windows", "Visibility")]
        assert field == "visible"
        assert transform(0) is True  # FullyVisible
        assert transform(1) is False  # Hidden
        assert transform(3) is True  # PartiallyVisible


# ---------------------------------------------------------------------------
# Linux AT-SPI state mappings
# ---------------------------------------------------------------------------


class TestLinuxStates:
    """Linux AT-SPI states → ElementStates fields."""

    def test_enabled(self) -> None:
        field, _ = STATE_MAP[("linux", "enabled")]
        assert field == "enabled"

    def test_focused(self) -> None:
        field, _ = STATE_MAP[("linux", "focused")]
        assert field == "focused"

    def test_selected(self) -> None:
        field, _ = STATE_MAP[("linux", "selected")]
        assert field == "selected"

    def test_checked(self) -> None:
        field, transform = STATE_MAP[("linux", "checked")]
        assert field == "checked"
        assert transform(0) is False
        assert transform(1) is True
        assert transform(2) == "mixed"

    def test_indeterminate(self) -> None:
        field, transform = STATE_MAP[("linux", "indeterminate")]
        assert field == "checked"
        assert transform(0) == "mixed"
        assert transform(1) == "mixed"

    def test_expanded(self) -> None:
        field, _ = STATE_MAP[("linux", "expanded")]
        assert field == "expanded"

    def test_visible_and_showing(self) -> None:
        assert STATE_MAP[("linux", "visible")][0] == "visible"
        assert STATE_MAP[("linux", "showing")][0] == "visible"

    def test_offscreen(self) -> None:
        field, _ = STATE_MAP[("linux", "offscreen")]
        assert field == "offscreen"

    def test_read_only_and_editable(self) -> None:
        assert STATE_MAP[("linux", "read-only")][0] == "read_only"
        editable_field, editable_transform = STATE_MAP[("linux", "editable")]
        assert editable_field == "read_only"
        assert editable_transform(True) is False
        assert editable_transform(False) is True

    def test_required(self) -> None:
        field, _ = STATE_MAP[("linux", "required")]
        assert field == "required"

    def test_modal(self) -> None:
        field, _ = STATE_MAP[("linux", "modal")]
        assert field == "modal"

    def test_focusable_selectable(self) -> None:
        assert STATE_MAP[("linux", "focusable")][0] == "focusable"
        assert STATE_MAP[("linux", "selectable")][0] == "selectable"


# ---------------------------------------------------------------------------
# Windows UIA action mappings
# ---------------------------------------------------------------------------


class TestWindowsActions:
    """Windows UIA patterns → normalized action string."""

    def test_invoke(self) -> None:
        assert ACTION_MAP[("windows", "InvokePattern")] == "invoke"

    def test_toggle(self) -> None:
        assert ACTION_MAP[("windows", "TogglePattern")] == "toggle"

    def test_select(self) -> None:
        assert ACTION_MAP[("windows", "SelectionItemPattern")] == "select"
        assert ACTION_MAP[("windows", "SelectionPattern")] == "select"

    def test_expand_collapse(self) -> None:
        assert ACTION_MAP[("windows", "ExpandCollapsePattern")] == "expand"

    def test_scroll(self) -> None:
        assert ACTION_MAP[("windows", "ScrollPattern")] == "scroll"

    def test_set_value(self) -> None:
        assert ACTION_MAP[("windows", "ValuePattern")] == "set_value"
        assert ACTION_MAP[("windows", "RangeValuePattern")] == "set_value"

    def test_type(self) -> None:
        assert ACTION_MAP[("windows", "TextPattern")] == "type"

    def test_convenience_aliases(self) -> None:
        assert ACTION_MAP[("windows", "Click")] == "click"
        assert ACTION_MAP[("windows", "Focus")] == "focus"
        assert ACTION_MAP[("windows", "Type")] == "type"
        assert ACTION_MAP[("windows", "SetValue")] == "set_value"
        assert ACTION_MAP[("windows", "Select")] == "select"
        assert ACTION_MAP[("windows", "Scroll")] == "scroll"
        assert ACTION_MAP[("windows", "Expand")] == "expand"
        assert ACTION_MAP[("windows", "Collapse")] == "collapse"
        assert ACTION_MAP[("windows", "Increment")] == "increment"
        assert ACTION_MAP[("windows", "Decrement")] == "decrement"


# ---------------------------------------------------------------------------
# Linux AT-SPI action mappings
# ---------------------------------------------------------------------------


class TestLinuxActions:
    """Linux AT-SPI actions → normalized action string."""

    def test_click(self) -> None:
        assert ACTION_MAP[("linux", "click")] == "click"
        assert ACTION_MAP[("linux", "press")] == "click"

    def test_activate(self) -> None:
        assert ACTION_MAP[("linux", "activate")] == "invoke"
        assert ACTION_MAP[("linux", "doAction")] == "invoke"

    def test_toggle(self) -> None:
        assert ACTION_MAP[("linux", "toggle")] == "toggle"

    def test_select(self) -> None:
        assert ACTION_MAP[("linux", "select")] == "select"
        assert ACTION_MAP[("linux", "deselect")] == "select"

    def test_scroll(self) -> None:
        assert ACTION_MAP[("linux", "scroll")] == "scroll"
        assert ACTION_MAP[("linux", "scrollUp")] == "scroll"
        assert ACTION_MAP[("linux", "scrollDown")] == "scroll"
        assert ACTION_MAP[("linux", "scrollLeft")] == "scroll"
        assert ACTION_MAP[("linux", "scrollRight")] == "scroll"

    def test_expand_collapse(self) -> None:
        assert ACTION_MAP[("linux", "expand")] == "expand"
        assert ACTION_MAP[("linux", "collapse")] == "collapse"

    def test_increment_decrement(self) -> None:
        assert ACTION_MAP[("linux", "increment")] == "increment"
        assert ACTION_MAP[("linux", "decrement")] == "decrement"

    def test_edit(self) -> None:
        assert ACTION_MAP[("linux", "edit")] == "type"
        assert ACTION_MAP[("linux", "insert")] == "type"


# ---------------------------------------------------------------------------
# Resolver helpers
# ---------------------------------------------------------------------------


class TestResolveRole:
    """Tests for the resolve_role() function."""

    def test_windows_resolve(self) -> None:
        assert resolve_role("windows", "Button") == "button"
        assert resolve_role("windows", "ControlType.Edit") == "text_input"

    def test_linux_resolve(self) -> None:
        assert resolve_role("linux", "push button") == "button"
        assert resolve_role("linux", "entry") == "text_input"

    def test_unknown_platform(self) -> None:
        assert resolve_role("freebsd", "Button") is None

    def test_unknown_role(self) -> None:
        assert resolve_role("windows", "NonExistentType") is None

    def test_case_insensitive_platform(self) -> None:
        assert resolve_role("Windows", "Button") == "button"
        assert resolve_role("LINUX", "push button") == "button"


class TestResolveState:
    """Tests for the resolve_state() function."""

    def test_windows_enabled(self) -> None:
        result = resolve_state("windows", "IsEnabled", True)
        assert result == ("enabled", True)

    def test_windows_toggle(self) -> None:
        result = resolve_state("windows", "ToggleState", 2)
        assert result == ("checked", "mixed")

    def test_linux_checked(self) -> None:
        result = resolve_state("linux", "checked", 0)
        assert result == ("checked", False)

    def test_unknown_platform(self) -> None:
        assert resolve_state("freebsd", "enabled", True) is None

    def test_unknown_state(self) -> None:
        assert resolve_state("windows", "NonExistentProp", True) is None

    def test_case_insensitive_platform(self) -> None:
        assert resolve_state("Windows", "IsEnabled", False) == ("enabled", False)
        assert resolve_state("LINUX", "enabled", True) == ("enabled", True)

    def test_state_with_no_transform(self) -> None:
        result = resolve_state("linux", "value", 42)
        assert result == ("value", 42)


class TestResolveAction:
    """Tests for the resolve_action() function."""

    def test_windows_resolve(self) -> None:
        assert resolve_action("windows", "InvokePattern") == "invoke"
        assert resolve_action("windows", "Click") == "click"

    def test_linux_resolve(self) -> None:
        assert resolve_action("linux", "click") == "click"
        assert resolve_action("linux", "toggle") == "toggle"

    def test_unknown_platform(self) -> None:
        assert resolve_action("freebsd", "click") is None

    def test_unknown_action(self) -> None:
        assert resolve_action("windows", "NonExistentPattern") is None

    def test_case_insensitive_platform(self) -> None:
        assert resolve_action("Windows", "Click") == "click"
        assert resolve_action("LINUX", "click") == "click"
