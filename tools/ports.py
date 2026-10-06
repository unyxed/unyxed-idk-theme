"""App ports generated from palettes.json. Imported by tools/build.py; never run on its own.

Every port is built from the 13 palette roles and the colors build.py already derives (the ANSI
slots, Zed's syntax groups), so a color fixed in palettes.json reaches every app on the next build.

Each generator takes a variant (or a group of variants) and a `Need` checker. It returns the
files to write and records readability checks with `need(fg, bg, floor, what)`; build.py turns a
failed check into a build error, like the terminal and Claude Code checks.
"""
import io
import json
import plistlib
import re
import zipfile

import build as B

# ---------------------------------------------------------------- shared helpers


class Need:
    """Collects readability problems (same floors as the terminal: 4.5 text, 3.5 faint)."""

    def __init__(self):
        self.problems = []

    def __call__(self, name, fg, bg, floor, what):
        got = B.contrast(fg[:7], bg[:7])
        if got + 1e-9 < floor:
            self.problems.append(f"{name}: {what} is {got:.2f}:1, needs {floor}")


class Ctx:
    """Everything a port needs about one variant: palette roles plus derived colors."""

    def __init__(self, v):
        self.v, self.name = v, v["name"]
        self.c = c = v["colors"]
        self.dark, self.r = B.is_dark(v), v["_rules"]
        self.slug = B.slug(v["name"])
        for k in B.ROLES:
            setattr(self, k, c[k])
        self.ansi = B.ansi(c, self.dark, self.r)
        self.syn = B.zed_syntax(c, self.r)
        bg, panel, tx = c["bg"], c["panel"], c["tx"]
        # the same derived UI colors Zed uses (see zed_theme in build.py)
        self.border, self.bvar = B.mix(panel, tx, .14), B.mix(panel, tx, .08)
        self.elev = B.mix(bg, tx, .05) if self.dark else B.mix(bg, "#FFFFFF", .35)
        self.el_bg, self.el_h, self.el_a = B.mix(bg, tx, .06), B.mix(bg, tx, .10), B.mix(bg, tx, .14)
        self.p_h, self.p_a = B.mix(panel, tx, .08), B.mix(panel, tx, .13)  # hover/active on panels
        self.muted, self.dis, self.icon = B.mix(tx, bg, .35), B.mix(tx, bg, .6), B.mix(tx, bg, .2)
        self.linenum = B.mix(c["cm"], bg, .2)
        # secondary text (inactive tabs, status bars) sits on bg and on panel: keep it readable on both
        for back in (bg, panel):
            self.muted = B.readable(self.muted, back, self.r["ansi"], self.dark)
        self.guide, self.guide_a = B.mix(bg, tx, .08), B.mix(bg, tx, .20)
        self.line_bg = B.mix(bg, tx, .05)
        self.far = "#FFFFFF" if self.dark else "#000000"
        self.shadow = "#00000059" if self.dark else "#0000001F"

    def on(self, col):
        """Readable label color on top of `col`: bg or tx, else black or white."""
        for cand in sorted((self.bg, self.tx), key=lambda x: -B.contrast(x, col)):
            if B.contrast(cand, col) >= self.r["ansi"]:
                return cand
        return max(("#000000", "#FFFFFF"), key=lambda x: B.contrast(x, col))

    def ink(self, col, *backs, floor=None):
        """col nudged (same hue) until readable on every background in `backs`."""
        floor = floor or self.r["ansi"]
        for b in backs:
            col = B.readable(col, b[:7], floor, B.lum(b[:7]) < 0.18)
        return col

    def fade(self, col, a, base=None, fg=None):
        """col at alpha `a` (as #RRGGBBAA), lowered until fg stays readable on it over base."""
        base, fg = base or self.bg, fg or self.tx
        while a > 0.05 and B.contrast(fg, B.over(base, B.alpha(col, a))) < self.r["ansi"]:
            a -= 0.01
        return B.alpha(col, a)

    def tok(self, cap):
        """Zed syntax style for a capture, resolved with Zed's longest-prefix rule."""
        k = B.resolve_key(self.syn, cap)
        return self.syn[k] if k else {"color": self.tx}

    def tcol(self, cap):
        return self.tok(cap)["color"]


def flat(base, col):
    """Opaque color of a possibly translucent #RRGGBBAA drawn on base."""
    return B.over(base[:7], col) if len(col) == 9 else col


def rgb(col):
    return list(B.h2r(col))


def units(fam):
    """Same grouping as the Obsidian snippets: one file per family, unless two variants share
    an appearance, then one per variant."""
    return B.obsidian_units(fam)


def version():
    m = re.search(r'^version\s*=\s*"([^"]+)"', (B.ROOT / "extension.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "0.0.0"


def zip_bytes(files):
    """Deterministic zip (fixed timestamps, stored, sorted) so rebuilding gives identical bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for path in sorted(files):
            info = zipfile.ZipInfo(path, date_time=(2024, 1, 1, 0, 0, 0))
            info.create_system, info.external_attr = 3, 0o644 << 16
            data = files[path]
            z.writestr(info, data.encode("utf-8") if isinstance(data, str) else data)
    return buf.getvalue()


# ---------------------------------------------------------------- TextMate scopes
# Zed capture -> TextMate scopes, used by VS Code and the .tmTheme (bat, delta, Sublime).
# Grouped exactly like Zed's Gruvbox (see GROUPS in build.py): the capture on the left is looked
# up in our Zed syntax, so a scope always gets the color Zed gives the same kind of token.
TM_SCOPES = [
    ("variable", ["variable", "variable.other", "variable.other.readwrite", "meta.definition.variable",
                  "support.variable"]),
    ("variable.parameter", ["variable.parameter", "meta.parameter", "entity.name.variable.parameter"]),
    ("property", ["variable.other.property", "variable.other.object.property", "variable.other.member",
                  "support.variable.property", "meta.object-literal.key", "support.type.property-name",
                  "entity.name.variable.field", "entity.name.tag.yaml"]),
    ("keyword", ["keyword", "keyword.control", "keyword.other", "keyword.operator.new", "keyword.operator.expression",
                 "keyword.operator.word", "keyword.operator.sizeof", "keyword.operator.cast", "keyword.operator.delete",
                 "keyword.operator.wordlike", "keyword.operator.logical.python", "storage", "storage.type",
                 "storage.modifier", "keyword.control.import", "keyword.control.export", "keyword.control.at-rule"]),
    ("preproc", ["meta.preprocessor", "keyword.control.directive", "punctuation.definition.directive"]),
    ("function.builtin", ["support.function.builtin", "support.function.magic"]),
    ("function", ["entity.name.function", "support.function", "meta.function-call.generic", "variable.function",
                  "entity.name.function.member", "support.function.any-method"]),
    ("string", ["string", "string.quoted", "string.template", "punctuation.definition.string", "constant.character"]),
    ("title", ["markup.heading", "entity.name.section", "punctuation.definition.heading"]),
    ("type", ["entity.name.type", "entity.name.class", "entity.name.struct", "entity.name.union",
              "entity.name.interface", "entity.name.trait", "entity.other.inherited-class", "support.type",
              "support.class", "storage.type.primitive", "storage.type.built-in", "storage.type.numeric",
              "storage.type.string", "storage.type.boolean", "storage.type.byte", "storage.type.rune",
              "storage.type.error", "storage.type.uintptr", "keyword.type", "entity.name.type.primitive",
              "entity.name.type.numeric", "support.type.primitive", "support.type.builtin"]),
    ("constant", ["constant", "constant.other", "variable.other.constant", "support.constant", "entity.name.constant",
                  "constant.language.null", "constant.language.undefined", "constant.language.nil",
                  "constant.language.none", "constant.language.nullptr", "entity.name.function.preprocessor"]),
    ("selector", ["meta.selector", "entity.name.tag.css", "entity.name.tag.scss", "entity.name.tag.less",
                  "entity.other.attribute-name.class.css", "entity.other.attribute-name.id.css",
                  "entity.other.attribute-name.class.scss", "entity.other.attribute-name.class.less"]),
    ("selector.pseudo", ["entity.other.attribute-name.pseudo-class", "entity.other.attribute-name.pseudo-element"]),
    ("attribute", ["entity.other.attribute-name", "meta.decorator", "punctuation.decorator",
                   "entity.name.function.decorator", "storage.type.annotation", "punctuation.definition.annotation",
                   "meta.annotation", "meta.attribute"]),
    ("constructor", ["entity.name.function.constructor", "support.function.constructor"]),
    ("namespace", ["entity.name.namespace", "entity.name.module", "entity.name.type.namespace",
                   "entity.name.type.module", "support.other.namespace", "entity.name.package",
                   "storage.modifier.import", "storage.modifier.package", "entity.name.scope-resolution"]),
    ("label", ["entity.name.label", "punctuation.definition.label"]),
    ("variant", ["variable.other.enummember", "entity.name.variant", "constant.other.enum"]),
    ("enum", ["entity.name.type.enum", "entity.name.enum", "support.type.enum"]),
    ("variable.special", ["variable.language", "variable.parameter.function.language.special.self"]),
    ("lifetime", ["storage.modifier.lifetime", "entity.name.type.lifetime", "punctuation.definition.lifetime"]),
    ("string.regex", ["string.regexp", "constant.other.character-class.regexp"]),
    ("string.escape", ["constant.character.escape", "constant.other.placeholder", "constant.character.format.placeholder"]),
    ("number", ["constant.numeric", "keyword.other.unit"]),
    ("boolean", ["constant.language", "constant.language.boolean"]),
    ("string.special", ["string.other", "string.unquoted.heredoc"]),
    ("string.special.symbol", ["constant.other.symbol", "constant.language.symbol"]),
    ("link_uri", ["markup.underline.link", "string.other.link.destination"]),
    ("link_text", ["string.other.link", "string.other.link.title", "string.other.link.description", "markup.link"]),
    ("operator", ["keyword.operator", "keyword.operator.assignment", "keyword.operator.arithmetic",
                  "keyword.operator.comparison", "keyword.operator.logical"]),
    ("tag", ["entity.name.tag"]),
    ("emphasis", ["markup.italic"]),
    ("emphasis.strong", ["markup.bold"]),
    ("text.literal", ["markup.inline.raw", "markup.raw", "markup.fixed"]),
    ("punctuation.list_marker", ["punctuation.definition.list.begin", "punctuation.definition.list",
                                 "beginning.punctuation.definition.list"]),
    ("punctuation", ["punctuation", "punctuation.separator", "punctuation.terminator", "meta.brace"]),
    ("punctuation.bracket", ["punctuation.definition.tag", "meta.brace.round", "meta.brace.square", "meta.brace.curly",
                             "punctuation.section", "punctuation.definition.block", "punctuation.definition.parameters",
                             "punctuation.definition.arguments"]),
    ("punctuation.delimiter", ["punctuation.separator.delimiter", "punctuation.terminator.statement",
                               "punctuation.separator.comma", "punctuation.accessor"]),
    ("punctuation.special", ["punctuation.definition.template-expression", "punctuation.section.embedded",
                             "punctuation.section.interpolation", "punctuation.definition.interpolation"]),
    ("comment", ["comment", "punctuation.definition.comment", "markup.quote"]),
    ("comment.doc", ["comment.block.documentation", "comment.line.documentation", "comment.block.javadoc",
                     "comment.line.double-slash.documentation", "storage.type.class.jsdoc",
                     "punctuation.definition.block.tag.jsdoc"]),
    ("diff.plus", ["markup.inserted", "meta.diff.header.to-file"]),
    ("diff.minus", ["markup.deleted", "meta.diff.header.from-file"]),
    ("diff.delta", ["markup.changed"]),
]
TM_STYLE = {"emphasis": "italic", "emphasis.strong": "bold", "title": "bold", "comment": "italic",
            "comment.doc": "italic", "link_uri": "underline", "link_text": "italic"}


def tm_rules(k):
    """[(name, scopes, color, fontStyle)] for TextMate-based ports."""
    out = []
    for cap, scopes in TM_SCOPES:
        st = k.tok(cap)
        style = TM_STYLE.get(cap, "")
        out.append((cap, scopes, st["color"], style))
    out.append(("invalid", ["invalid", "invalid.illegal"], k.red, "underline"))
    out.append(("deprecated", ["invalid.deprecated"], k.cm, "strikethrough"))
    return out


# ---------------------------------------------------------------- VS Code
def vscode_theme(k, need):
    bg, panel, tx, cm, sel, acc = k.bg, k.panel, k.tx, k.cm, k.sel, k.accent
    red, orange, yellow, green, aqua, blue, purple = k.red, k.orange, k.yellow, k.green, k.aqua, k.blue, k.purple
    A = B.alpha
    on_acc = k.on(acc)
    acc_on_sel = k.ink(acc, sel)
    acc_on_panel = k.ink(acc, panel, k.elev)
    side_sel = B.mix(sel, panel, .35)
    bracket = k.tcol("punctuation.bracket")
    col = {
        # base
        "focusBorder": A(acc, .8), "foreground": tx, "disabledForeground": k.dis, "descriptionForeground": k.muted,
        "errorForeground": red, "icon.foreground": k.icon, "selection.background": A(acc, .35),
        "widget.border": k.border, "widget.shadow": k.shadow, "sash.hoverBorder": acc,
        "textLink.foreground": blue, "textLink.activeForeground": aqua, "textCodeBlock.background": k.el_bg,
        "textBlockQuote.background": panel, "textBlockQuote.border": acc, "textPreformat.foreground": blue,
        "textPreformat.background": k.el_bg, "textSeparator.foreground": k.border,
        # controls
        "button.background": acc, "button.foreground": on_acc, "button.hoverBackground": B.mix(acc, tx, .15),
        "button.border": "#00000000", "button.separator": A(on_acc, .4),
        "button.secondaryBackground": k.el_h, "button.secondaryForeground": tx, "button.secondaryHoverBackground": k.el_a,
        "checkbox.background": k.el_bg, "checkbox.border": k.border, "checkbox.foreground": tx,
        "dropdown.background": k.elev, "dropdown.border": k.border, "dropdown.foreground": tx,
        "dropdown.listBackground": k.elev,
        "input.background": k.el_bg, "input.border": k.border, "input.foreground": tx,
        "input.placeholderForeground": cm, "inputOption.activeBackground": A(acc, .25),
        "inputOption.activeBorder": acc, "inputOption.activeForeground": tx, "inputOption.hoverBackground": k.el_h,
        "inputValidation.errorBackground": B.mix(bg, red, .14), "inputValidation.errorBorder": red,
        "inputValidation.errorForeground": tx,
        "inputValidation.warningBackground": B.mix(bg, yellow, .14), "inputValidation.warningBorder": yellow,
        "inputValidation.warningForeground": tx,
        "inputValidation.infoBackground": B.mix(bg, blue, .14), "inputValidation.infoBorder": blue,
        "inputValidation.infoForeground": tx,
        "badge.background": acc, "badge.foreground": on_acc, "progressBar.background": acc,
        "scrollbar.shadow": "#00000000", "scrollbarSlider.background": A(tx, .15),
        "scrollbarSlider.hoverBackground": A(tx, .3), "scrollbarSlider.activeBackground": A(acc, .6),
        "keybindingLabel.background": k.el_bg, "keybindingLabel.foreground": tx, "keybindingLabel.border": k.border,
        "keybindingLabel.bottomBorder": k.border,
        # lists and trees
        "list.activeSelectionBackground": sel, "list.activeSelectionForeground": tx,
        "list.activeSelectionIconForeground": tx, "list.inactiveSelectionBackground": side_sel,
        "list.inactiveSelectionForeground": tx, "list.hoverBackground": k.p_h, "list.hoverForeground": tx,
        "list.focusBackground": sel, "list.focusForeground": tx, "list.focusOutline": A(acc, .8),
        "list.focusAndSelectionOutline": A(acc, .8), "list.inactiveFocusOutline": k.border,
        "list.highlightForeground": acc_on_panel, "list.focusHighlightForeground": acc_on_sel,
        "list.errorForeground": red, "list.warningForeground": yellow, "list.invalidItemForeground": red,
        "list.deemphasizedForeground": cm, "list.dropBackground": A(acc, .2),
        "listFilterWidget.background": k.elev, "listFilterWidget.outline": acc,
        "listFilterWidget.noMatchesOutline": red, "tree.indentGuidesStroke": k.border,
        "tree.inactiveIndentGuidesStroke": k.bvar,
        # workbench parts
        "activityBar.background": panel, "activityBar.foreground": tx, "activityBar.inactiveForeground": cm,
        "activityBar.border": k.bvar, "activityBar.activeBorder": acc, "activityBar.activeBackground": "#00000000",
        "activityBarBadge.background": acc, "activityBarBadge.foreground": on_acc,
        "activityBarTop.foreground": tx, "activityBarTop.inactiveForeground": cm, "activityBarTop.activeBorder": acc,
        "sideBar.background": panel, "sideBar.foreground": tx, "sideBar.border": k.bvar,
        "sideBarTitle.foreground": tx, "sideBarSectionHeader.background": panel,
        "sideBarSectionHeader.foreground": tx, "sideBarSectionHeader.border": k.bvar,
        "sideBarActivityBarTop.border": k.bvar, "sideBarStickyScroll.background": panel,
        "editorGroup.border": k.border, "editorGroup.dropBackground": A(acc, .15),
        "editorGroupHeader.tabsBackground": panel, "editorGroupHeader.tabsBorder": k.bvar,
        "editorGroupHeader.noTabsBackground": bg, "editorGroupHeader.border": k.bvar,
        "tab.activeBackground": bg, "tab.activeForeground": tx, "tab.activeBorderTop": acc, "tab.activeBorder": bg,
        "tab.inactiveBackground": panel, "tab.inactiveForeground": k.muted, "tab.border": k.bvar,
        "tab.hoverBackground": k.p_h, "tab.hoverForeground": tx, "tab.unfocusedActiveForeground": k.muted,
        "tab.unfocusedInactiveForeground": cm, "tab.unfocusedActiveBorderTop": k.border,
        "tab.unfocusedHoverBackground": k.p_h, "tab.modifiedBorder": yellow, "tab.lastPinnedBorder": k.border,
        "tab.selectedBackground": bg, "tab.selectedForeground": tx, "tab.selectedBorderTop": acc,
        "panel.background": panel, "panel.border": k.bvar, "panelTitle.activeBorder": acc,
        "panelTitle.activeForeground": tx, "panelTitle.inactiveForeground": k.muted, "panelInput.border": k.border,
        "panelSection.border": k.bvar, "panelSectionHeader.background": panel, "panelStickyScroll.background": panel,
        "statusBar.background": panel, "statusBar.foreground": k.muted, "statusBar.border": k.bvar,
        "statusBar.focusBorder": acc, "statusBar.noFolderBackground": panel, "statusBar.noFolderForeground": k.muted,
        "statusBar.debuggingBackground": orange, "statusBar.debuggingForeground": k.on(orange),
        "statusBar.debuggingBorder": orange,
        "statusBarItem.hoverBackground": k.p_h, "statusBarItem.hoverForeground": tx,
        "statusBarItem.activeBackground": k.p_a, "statusBarItem.remoteBackground": acc,
        "statusBarItem.remoteForeground": on_acc, "statusBarItem.remoteHoverBackground": B.mix(acc, tx, .15),
        "statusBarItem.remoteHoverForeground": on_acc,
        "statusBarItem.errorBackground": red, "statusBarItem.errorForeground": k.on(red),
        "statusBarItem.warningBackground": yellow, "statusBarItem.warningForeground": k.on(yellow),
        "statusBarItem.prominentBackground": sel, "statusBarItem.prominentForeground": tx,
        "statusBarItem.prominentHoverBackground": k.p_a,
        "titleBar.activeBackground": panel, "titleBar.activeForeground": tx, "titleBar.inactiveBackground": panel,
        "titleBar.inactiveForeground": cm, "titleBar.border": k.bvar,
        "commandCenter.background": k.p_h, "commandCenter.foreground": k.muted, "commandCenter.border": k.bvar,
        "commandCenter.activeBackground": k.p_a, "commandCenter.activeForeground": tx,
        "commandCenter.inactiveForeground": cm, "commandCenter.inactiveBorder": k.bvar,
        "menubar.selectionBackground": k.p_h, "menubar.selectionForeground": tx,
        "menu.background": k.elev, "menu.foreground": tx, "menu.selectionBackground": sel,
        "menu.selectionForeground": tx, "menu.separatorBackground": k.border, "menu.border": k.border,
        "quickInput.background": k.elev, "quickInput.foreground": tx, "quickInputTitle.background": panel,
        "quickInputList.focusBackground": sel, "quickInputList.focusForeground": tx,
        "quickInputList.focusIconForeground": tx, "pickerGroup.foreground": acc_on_panel, "pickerGroup.border": k.border,
        "notifications.background": k.elev, "notifications.foreground": tx, "notifications.border": k.border,
        "notificationCenterHeader.background": panel, "notificationCenterHeader.foreground": tx,
        "notificationLink.foreground": blue, "notificationToast.border": k.border,
        "notificationsErrorIcon.foreground": red, "notificationsWarningIcon.foreground": yellow,
        "notificationsInfoIcon.foreground": blue,
        "breadcrumb.foreground": k.muted, "breadcrumb.background": bg, "breadcrumb.focusForeground": tx,
        "breadcrumb.activeSelectionForeground": tx, "breadcrumbPicker.background": k.elev,
        "settings.headerForeground": tx, "settings.modifiedItemIndicator": acc,
        "settings.focusedRowBackground": k.line_bg, "settings.rowHoverBackground": k.line_bg,
        "settings.focusedRowBorder": A(acc, .6), "settings.headerBorder": k.border,
        "settings.sashBorder": k.border, "settings.dropdownBackground": k.elev, "settings.dropdownBorder": k.border,
        "settings.textInputBackground": k.el_bg, "settings.textInputBorder": k.border,
        "settings.numberInputBackground": k.el_bg, "settings.numberInputBorder": k.border,
        "settings.checkboxBackground": k.el_bg, "settings.checkboxBorder": k.border,
        "welcomePage.tileBackground": panel, "welcomePage.tileHoverBackground": k.p_h,
        "welcomePage.tileBorder": k.border, "walkThrough.embeddedEditorBackground": panel,
        "debugToolBar.background": k.elev, "debugToolBar.border": k.border,
        "debugIcon.breakpointForeground": red, "debugIcon.breakpointDisabledForeground": cm,
        "debugIcon.startForeground": green, "debugIcon.pauseForeground": yellow, "debugIcon.stopForeground": red,
        "debugIcon.restartForeground": green, "debugIcon.continueForeground": green,
        "debugIcon.stepOverForeground": blue, "debugIcon.stepIntoForeground": blue, "debugIcon.stepOutForeground": blue,
        "testing.iconPassed": green, "testing.iconFailed": red, "testing.iconErrored": red,
        "testing.iconQueued": yellow, "testing.iconSkipped": cm, "testing.iconUnset": cm,
        "testing.runAction": green,
        "charts.foreground": tx, "charts.lines": k.border, "charts.red": red, "charts.orange": orange,
        "charts.yellow": yellow, "charts.green": green, "charts.blue": blue, "charts.purple": purple,
        "extensionButton.prominentBackground": acc, "extensionButton.prominentForeground": on_acc,
        "extensionButton.prominentHoverBackground": B.mix(acc, tx, .15), "extensionBadge.remoteBackground": acc,
        "extensionBadge.remoteForeground": on_acc, "extensionIcon.starForeground": yellow,
        "gitDecoration.addedResourceForeground": green, "gitDecoration.modifiedResourceForeground": yellow,
        "gitDecoration.deletedResourceForeground": red, "gitDecoration.renamedResourceForeground": blue,
        "gitDecoration.untrackedResourceForeground": green, "gitDecoration.ignoredResourceForeground": cm,
        "gitDecoration.conflictingResourceForeground": orange, "gitDecoration.submoduleResourceForeground": blue,
        "gitDecoration.stageModifiedResourceForeground": yellow,
        "gitDecoration.stageDeletedResourceForeground": red,
        "scmGraph.historyItemRefColor": blue, "scmGraph.historyItemRemoteRefColor": purple,
        "scmGraph.historyItemBaseRefColor": orange, "scmGraph.historyItemHoverDefaultLabelForeground": tx,
        "chat.requestBackground": k.line_bg, "chat.requestBorder": k.bvar, "chat.slashCommandForeground": blue,
        "chat.avatarBackground": k.el_h, "chat.avatarForeground": tx,
        # editor
        "editor.background": bg, "editor.foreground": tx, "editorLineNumber.foreground": k.linenum,
        "editorLineNumber.activeForeground": tx, "editorLineNumber.dimmedForeground": k.guide_a,
        "editorCursor.foreground": acc, "editorCursor.background": bg, "editorMultiCursor.primary.foreground": acc,
        "editorMultiCursor.secondary.foreground": blue,
        "editor.selectionBackground": A(acc, .25), "editor.selectionForeground": tx,
        "editor.inactiveSelectionBackground": A(acc, .13), "editor.selectionHighlightBackground": A(blue, .15),
        "editor.selectionHighlightBorder": "#00000000",
        "editor.wordHighlightBackground": A(blue, .15), "editor.wordHighlightStrongBackground": A(acc, .2),
        "editor.wordHighlightTextBackground": A(blue, .15),
        "editor.findMatchBackground": A(orange, .45), "editor.findMatchBorder": "#00000000",
        "editor.findMatchHighlightBackground": A(blue, .3), "editor.findRangeHighlightBackground": A(sel, .6),
        "editor.hoverHighlightBackground": A(blue, .15), "editor.lineHighlightBackground": k.line_bg,
        "editor.lineHighlightBorder": "#00000000", "editor.rangeHighlightBackground": A(yellow, .1),
        "editor.symbolHighlightBackground": A(orange, .3), "editor.linkedEditingBackground": A(acc, .15),
        "editor.foldBackground": A(blue, .08), "editor.snippetTabstopHighlightBackground": A(blue, .2),
        "editor.stackFrameHighlightBackground": A(yellow, .15),
        "editor.focusedStackFrameHighlightBackground": A(green, .15),
        "editorLink.activeForeground": blue, "editorWhitespace.foreground": k.guide_a,
        "editorIndentGuide.background1": k.guide, "editorIndentGuide.activeBackground1": k.guide_a,
        "editorRuler.foreground": k.guide, "editorCodeLens.foreground": cm,
        "editorBracketMatch.background": A(acc, .2), "editorBracketMatch.border": A(acc, .6),
        "editorUnicodeHighlight.border": yellow,
        "editorOverviewRuler.border": "#00000000", "editorOverviewRuler.background": bg,
        "editorOverviewRuler.findMatchForeground": A(orange, .7), "editorOverviewRuler.errorForeground": red,
        "editorOverviewRuler.warningForeground": yellow, "editorOverviewRuler.infoForeground": blue,
        "editorOverviewRuler.addedForeground": A(green, .7), "editorOverviewRuler.modifiedForeground": A(yellow, .7),
        "editorOverviewRuler.deletedForeground": A(red, .7), "editorOverviewRuler.selectionHighlightForeground": A(acc, .6),
        "editorOverviewRuler.bracketMatchForeground": A(acc, .6),
        "editorError.foreground": red, "editorWarning.foreground": yellow, "editorInfo.foreground": blue,
        "editorHint.foreground": k.tcol("hint"), "problemsErrorIcon.foreground": red,
        "problemsWarningIcon.foreground": yellow, "problemsInfoIcon.foreground": blue,
        "editorGutter.background": bg, "editorGutter.addedBackground": green,
        "editorGutter.modifiedBackground": yellow, "editorGutter.deletedBackground": red,
        "editorGutter.foldingControlForeground": cm, "editorGutter.commentRangeForeground": k.guide_a,
        "editorInlayHint.foreground": k.ink(cm, k.el_bg, floor=k.r["ansi_dim"]), "editorInlayHint.background": k.el_bg,
        "editorGhostText.foreground": k.tcol("predictive"), "editorLightBulb.foreground": yellow,
        "editorLightBulbAutoFix.foreground": blue,
        "editorStickyScroll.background": bg, "editorStickyScrollHover.background": k.line_bg,
        "editorStickyScroll.shadow": k.shadow, "editorStickyScroll.border": k.bvar,
        "editorWidget.background": k.elev, "editorWidget.foreground": tx, "editorWidget.border": k.border,
        "editorWidget.resizeBorder": acc,
        "editorSuggestWidget.background": k.elev, "editorSuggestWidget.border": k.border,
        "editorSuggestWidget.foreground": tx, "editorSuggestWidget.highlightForeground": k.ink(acc, k.elev),
        "editorSuggestWidget.focusHighlightForeground": acc_on_sel, "editorSuggestWidget.selectedBackground": sel,
        "editorSuggestWidget.selectedForeground": tx, "editorSuggestWidget.selectedIconForeground": tx,
        "editorHoverWidget.background": k.elev, "editorHoverWidget.foreground": tx,
        "editorHoverWidget.border": k.border, "editorHoverWidget.highlightForeground": k.ink(acc, k.elev),
        "editorHoverWidget.statusBarBackground": panel,
        "editorMarkerNavigation.background": k.elev, "editorMarkerNavigationError.background": red,
        "editorMarkerNavigationWarning.background": yellow, "editorMarkerNavigationInfo.background": blue,
        "peekView.border": acc, "peekViewEditor.background": panel, "peekViewEditorGutter.background": panel,
        "peekViewEditor.matchHighlightBackground": A(orange, .35), "peekViewResult.background": panel,
        "peekViewResult.fileForeground": tx, "peekViewResult.lineForeground": k.muted,
        "peekViewResult.matchHighlightBackground": A(orange, .35), "peekViewResult.selectionBackground": sel,
        "peekViewResult.selectionForeground": tx, "peekViewTitle.background": panel,
        "peekViewTitleLabel.foreground": tx, "peekViewTitleDescription.foreground": k.muted,
        "diffEditor.insertedTextBackground": A(green, .2), "diffEditor.removedTextBackground": A(red, .2),
        "diffEditor.insertedLineBackground": A(green, .1), "diffEditor.removedLineBackground": A(red, .1),
        "diffEditor.diagonalFill": k.bvar, "diffEditor.border": k.border,
        "diffEditorGutter.insertedLineBackground": A(green, .18), "diffEditorGutter.removedLineBackground": A(red, .18),
        "diffEditorOverview.insertedForeground": A(green, .6), "diffEditorOverview.removedForeground": A(red, .6),
        "merge.currentHeaderBackground": A(green, .35), "merge.currentContentBackground": A(green, .12),
        "merge.incomingHeaderBackground": A(blue, .35), "merge.incomingContentBackground": A(blue, .12),
        "merge.commonHeaderBackground": A(cm, .35), "merge.commonContentBackground": A(cm, .12),
        "minimap.background": bg, "minimap.selectionHighlight": A(acc, .4),
        "minimap.findMatchHighlight": A(orange, .6), "minimap.errorHighlight": A(red, .8),
        "minimap.warningHighlight": A(yellow, .8), "minimapSlider.background": A(tx, .1),
        "minimapSlider.hoverBackground": A(tx, .15), "minimapSlider.activeBackground": A(acc, .3),
        "minimapGutter.addedBackground": green, "minimapGutter.modifiedBackground": yellow,
        "minimapGutter.deletedBackground": red,
        "editorBracketHighlight.unexpectedBracket.foreground": red,
        # terminal: the same slots as Zed and Windows Terminal
        "terminal.background": bg, "terminal.foreground": tx, "terminalCursor.foreground": acc,
        "terminalCursor.background": bg, "terminal.selectionBackground": sel, "terminal.border": k.bvar,
        "terminal.tab.activeBorder": acc, "terminal.findMatchBackground": A(orange, .45),
        "terminal.findMatchHighlightBackground": A(blue, .3), "terminalCommandDecoration.defaultBackground": cm,
        "terminalCommandDecoration.successBackground": green, "terminalCommandDecoration.errorBackground": red,
        "terminalOverviewRuler.cursorForeground": acc,
    }
    # Zed does not colorize brackets: keep VS Code's bracket-pair colors on the dimmed bracket tone
    for i in range(1, 7):
        col[f"editorBracketHighlight.foreground{i}"] = bracket
        col[f"editorBracketPairGuide.activeBackground{i}"] = k.guide_a
        col[f"editorBracketPairGuide.background{i}"] = "#00000000"
    names = {"black": "Black", "red": "Red", "green": "Green", "yellow": "Yellow", "blue": "Blue",
             "magenta": "Magenta", "cyan": "Cyan", "white": "White"}
    for n, cap in names.items():
        col["terminal.ansi" + cap] = k.ansi[n]
        col["terminal.ansiBright" + cap] = k.ansi["bright_" + n]

    tokens = []
    for cap, scopes, color, style in tm_rules(k):
        s = {"foreground": color}
        if style:
            s["fontStyle"] = style
        tokens.append({"name": cap, "scope": scopes, "settings": s})
    semantic = {
        "namespace": k.tcol("namespace"), "type": k.yellow, "class": k.yellow, "struct": k.yellow,
        "interface": k.yellow, "typeParameter": k.yellow, "typeAlias": k.yellow, "builtinType": k.yellow,
        "concept": k.yellow, "enum": k.tcol("enum"), "enumMember": k.tcol("variant"),
        "parameter": tx, "variable": tx, "property": tx, "event": tx,
        "function": k.tcol("function"), "method": k.tcol("function"), "function.defaultLibrary": k.tcol("function.builtin"),
        "macro": k.tcol("constant"), "keyword": k.red, "modifier": k.red, "comment": {"foreground": cm, "fontStyle": "italic"},
        "string": k.tcol("string"), "number": k.tcol("number"), "boolean": k.tcol("boolean"),
        "regexp": k.tcol("string.regex"), "operator": k.tcol("operator"), "decorator": k.tcol("attribute"),
        "label": k.tcol("label"), "selfKeyword": k.tcol("variable.special"),
        "selfParameter": k.tcol("variable.special"), "lifetime": k.tcol("lifetime"),
        "variable.constant": None, "*.deprecated": {"fontStyle": "strikethrough"},
    }
    semantic = {kk: vv for kk, vv in semantic.items() if vv is not None}

    # readability checks (backgrounds flattened over what they sit on)
    n = k.name
    for fg, bgc, floor, what in [
        (tx, flat(bg, col["editor.selectionBackground"]), k.r["ansi"], "vscode text on the editor selection"),
        (on_acc, acc, k.r["ansi"], "vscode button text"), (tx, sel, k.r["ansi"], "vscode text on list selection"),
        (tx, side_sel, k.r["ansi"], "vscode text on inactive list selection"),
        (acc_on_sel, sel, k.r["ansi"], "vscode match highlight on selection"),
        (acc_on_panel, panel, k.r["ansi"], "vscode match highlight in the sidebar"),
        (k.muted, panel, k.r["ansi"], "vscode inactive tab and status bar text"),
        (cm, panel, k.r["ansi_dim"], "vscode inactive icons and titles"),
        (col["statusBarItem.errorForeground"], red, k.r["ansi"], "vscode status bar error text"),
        (col["statusBarItem.warningForeground"], yellow, k.r["ansi"], "vscode status bar warning text"),
        (col["statusBar.debuggingForeground"], orange, k.r["ansi"], "vscode debugging status bar text"),
        (col["editorInlayHint.foreground"], k.el_bg, k.r["ansi_dim"], "vscode inlay hints"),
    ]:
        need(n, fg, bgc, floor, what)
    return {"name": k.name, "type": "dark" if k.dark else "light", "semanticHighlighting": True,
            "colors": col, "tokenColors": tokens, "semanticTokenColors": semantic}


def vscode_package(pkg, data):
    vs = [v for _, v in B.variants(data)]
    manifest = {
        "name": pkg["id"], "displayName": pkg["name"], "description": f"{pkg['name']}, generated from palettes.json.",
        "version": version(), "publisher": pkg["author"], "license": "UNLICENSED",
        "engines": {"vscode": "^1.75.0"}, "categories": ["Themes"],
        "contributes": {"themes": [{"label": v["name"], "uiTheme": "vs-dark" if B.is_dark(v) else "vs",
                                    "path": f"./themes/{B.slug(v['name'])}.json"} for v in vs]},
    }
    return manifest


def vsix(pkg, manifest, theme_files):
    ver, ident = manifest["version"], pkg["id"]
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" '
           'xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">\n'
           f'  <Metadata>\n    <Identity Language="en-US" Id="{ident}" Version="{ver}" Publisher="{pkg["author"]}" />\n'
           f'    <DisplayName>{pkg["name"]}</DisplayName>\n'
           f'    <Description xml:space="preserve">{manifest["description"]}</Description>\n'
           '    <Tags>theme,color-theme</Tags>\n    <Categories>Themes</Categories>\n'
           '    <GalleryFlags>Public</GalleryFlags>\n    <Properties>\n'
           f'      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{manifest["engines"]["vscode"]}" />\n'
           '      <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />\n'
           '      <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />\n'
           '      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="ui,workspace,web" />\n'
           '      <Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value="" />\n'
           '    </Properties>\n  </Metadata>\n'
           '  <Installation>\n    <InstallationTarget Id="Microsoft.VisualStudio.Code" />\n  </Installation>\n'
           '  <Dependencies />\n  <Assets>\n'
           '    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />\n'
           '  </Assets>\n</PackageManifest>\n')
    types = ('<?xml version="1.0" encoding="utf-8"?>\n'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension=".json" ContentType="application/json" />'
             '<Default Extension=".vsixmanifest" ContentType="text/xml" /></Types>\n')
    files = {"extension.vsixmanifest": xml, "[Content_Types].xml": types,
             "extension/package.json": json.dumps(manifest, indent=2) + "\n"}
    for name, text in theme_files.items():
        files[f"extension/themes/{name}"] = text
    return zip_bytes(files)


# ---------------------------------------------------------------- TextMate theme (bat, delta, Sublime)
def tmtheme(k, need):
    settings = [{"settings": {
        "background": k.bg, "foreground": k.tx, "caret": k.accent, "selection": B.over(k.bg, B.alpha(k.accent, .25)),
        "selectionForeground": k.tx, "lineHighlight": k.line_bg, "invisibles": k.guide_a, "gutter": k.bg,
        "gutterForeground": k.linenum, "findHighlight": B.over(k.bg, B.alpha(k.orange, .45)),
        "findHighlightForeground": k.tx, "guide": k.guide, "activeGuide": k.guide_a, "bracketsForeground": k.accent,
        "misspelling": k.red}}]
    for cap, scopes, color, style in tm_rules(k):
        s = {"foreground": color}
        if style:
            s["fontStyle"] = style
        settings.append({"name": cap, "scope": ", ".join(scopes), "settings": s})
    doc = {"name": k.name, "author": "unyxed", "semanticClass": f"theme.{'dark' if k.dark else 'light'}.{k.slug}",
           "colorSpaceName": "sRGB", "settings": settings}
    return plistlib.dumps(doc, sort_keys=False).decode("utf-8")


def delta_gitconfig(pkg, data):
    out = [f"# {pkg['name']}: delta features, one per theme. Generated by tools/build.py; do not edit.",
           "# Include this file from ~/.gitconfig and pick a theme (see README):",
           "#   [include]", f"#       path = <this repo>/ports/delta/{pkg['id']}.gitconfig",
           "#   [delta]", "#       features = <theme-slug>", ""]
    for _, v in B.variants(data):
        k = Ctx(v)
        add, rem = B.tint(k.bg, k.green, .2, k.tx, k.r["ansi"]), B.tint(k.bg, k.red, .2, k.tx, k.r["ansi"])
        add_w, rem_w = B.tint(k.bg, k.green, .36, k.tx, k.r["ansi"]), B.tint(k.bg, k.red, .36, k.tx, k.r["ansi"])
        out += [f'[delta "{k.slug}"]', f"    {'dark' if k.dark else 'light'} = true",
                f"    syntax-theme = {k.name}",
                f'    minus-style = syntax "{rem}"', f'    minus-emph-style = syntax "{rem_w}"',
                f'    plus-style = syntax "{add}"', f'    plus-emph-style = syntax "{add_w}"',
                f'    map-styles = bold purple => syntax "{B.tint(k.bg, k.purple, .2, k.tx, k.r["ansi"])}", '
                f'bold cyan => syntax "{B.tint(k.bg, k.aqua, .2, k.tx, k.r["ansi"])}"',
                f'    line-numbers-minus-style = "{k.red}"', f'    line-numbers-plus-style = "{k.green}"',
                f'    line-numbers-zero-style = "{k.linenum}"',
                f'    line-numbers-left-style = "{k.bvar}"', f'    line-numbers-right-style = "{k.bvar}"',
                f'    file-style = "{k.tx}" bold', f'    file-decoration-style = "{k.border}" ul',
                f'    hunk-header-style = file line-number syntax',
                f'    hunk-header-decoration-style = "{k.border}" box', f'    hunk-header-line-number-style = "{k.blue}"',
                f'    commit-decoration-style = "{k.border}" box', f'    blame-palette = "{k.bg} {k.line_bg} {k.el_bg}"',
                ""]
    return "\n".join(out)


# ---------------------------------------------------------------- terminals
def ghostty(k, need):
    a = k.ansi
    lines = [f"# {k.name} for Ghostty. Generated by tools/build.py from palettes.json; do not edit.",
             f"background = {k.bg}", f"foreground = {k.tx}", f"cursor-color = {k.accent}",
             f"cursor-text = {k.on(k.accent)}", f"selection-background = {k.sel}", f"selection-foreground = {k.tx}",
             f"split-divider-color = {k.border}"]
    for i, n in enumerate(B.ANSI_NAMES):
        lines.append(f"palette = {i}={a[n]}")
    for i, n in enumerate(B.ANSI_NAMES):
        lines.append(f"palette = {i + 8}={a['bright_' + n]}")
    need(k.name, k.on(k.accent), k.accent, k.r["ansi"], "terminal text under the cursor")
    return "\n".join(lines) + "\n"


def kitty(k, need):
    a = k.ansi
    lines = [f"## name: {k.name}", "## author: unyxed", "## license: see repository",
             "## blurb: Generated by tools/build.py from palettes.json; do not edit.", "",
             f"foreground {k.tx}", f"background {k.bg}", f"selection_foreground {k.tx}",
             f"selection_background {k.sel}", f"cursor {k.accent}", f"cursor_text_color {k.on(k.accent)}",
             f"url_color {k.blue}", f"active_border_color {k.accent}", f"inactive_border_color {k.border}",
             f"bell_border_color {k.yellow}", f"visual_bell_color {k.el_a}",
             f"active_tab_foreground {k.tx}", f"active_tab_background {k.bg}",
             f"inactive_tab_foreground {k.muted}", f"inactive_tab_background {k.panel}",
             f"tab_bar_background {k.panel}", f"tab_bar_margin_color {k.panel}",
             f"mark1_foreground {k.on(k.blue)}", f"mark1_background {k.blue}",
             f"mark2_foreground {k.on(k.purple)}", f"mark2_background {k.purple}",
             f"mark3_foreground {k.on(k.orange)}", f"mark3_background {k.orange}", ""]
    for i, n in enumerate(B.ANSI_NAMES):
        lines.append(f"color{i} {a[n]}")
        lines.append(f"color{i + 8} {a['bright_' + n]}")
    need(k.name, k.muted, k.panel, k.r["ansi"], "kitty inactive tab text")
    return "\n".join(lines) + "\n"


def alacritty(k, need):
    a = k.ansi

    def table(title, prefix=""):
        rows = [f"[colors.{title}]"]
        for n in B.ANSI_NAMES:
            rows.append(f'{n} = "{a[prefix + n]}"')
        return rows
    lines = [f"# {k.name} for Alacritty. Generated by tools/build.py from palettes.json; do not edit.",
             "[colors.primary]", f'background = "{k.bg}"', f'foreground = "{k.tx}"',
             f'dim_foreground = "{B.soft(k.tx, k.bg, .35, k.r["ansi_dim"])}"', "",
             "[colors.cursor]", f'text = "{k.on(k.accent)}"', f'cursor = "{k.accent}"', "",
             "[colors.vi_mode_cursor]", f'text = "{k.on(k.blue)}"', f'cursor = "{k.blue}"', "",
             "[colors.selection]", f'text = "{k.tx}"', f'background = "{k.sel}"', "",
             "[colors.search.matches]", f'foreground = "{k.on(k.blue)}"', f'background = "{k.blue}"', "",
             "[colors.search.focused_match]", f'foreground = "{k.on(k.orange)}"', f'background = "{k.orange}"', "",
             "[colors.footer_bar]", f'foreground = "{k.tx}"', f'background = "{k.panel}"', "",
             "[colors.hints.start]", f'foreground = "{k.on(k.yellow)}"', f'background = "{k.yellow}"', "",
             "[colors.hints.end]", f'foreground = "{k.on(k.purple)}"', f'background = "{k.purple}"', ""]
    lines += table("normal") + [""] + table("bright", "bright_") + [""] + table("dim", "dim_")
    for col in (k.blue, k.orange, k.yellow, k.purple):
        need(k.name, k.on(col), col, k.r["ansi"], "alacritty label on a highlight")
    return "\n".join(lines) + "\n"


def wezterm(k, need):
    a = k.ansi

    def arr(prefix=""):
        return "[" + ", ".join(f'"{a[prefix + n]}"' for n in B.ANSI_NAMES) + "]"
    lines = [f"# {k.name} for WezTerm. Generated by tools/build.py from palettes.json; do not edit.",
             "[colors]", f'foreground = "{k.tx}"', f'background = "{k.bg}"', f'cursor_bg = "{k.accent}"',
             f'cursor_fg = "{k.on(k.accent)}"', f'cursor_border = "{k.accent}"', f'selection_fg = "{k.tx}"',
             f'selection_bg = "{k.sel}"', f'scrollbar_thumb = "{k.el_a}"', f'split = "{k.border}"',
             f'compose_cursor = "{k.orange}"', f'visual_bell = "{k.el_a}"',
             f"ansi = {arr()}", f"brights = {arr('bright_')}", "",
             "[colors.tab_bar]", f'background = "{k.panel}"', f'inactive_tab_edge = "{k.border}"', "",
             "[colors.tab_bar.active_tab]", f'bg_color = "{k.bg}"', f'fg_color = "{k.tx}"', "",
             "[colors.tab_bar.inactive_tab]", f'bg_color = "{k.panel}"', f'fg_color = "{k.muted}"', "",
             "[colors.tab_bar.inactive_tab_hover]", f'bg_color = "{k.p_h}"', f'fg_color = "{k.tx}"', "",
             "[colors.tab_bar.new_tab]", f'bg_color = "{k.panel}"', f'fg_color = "{k.muted}"', "",
             "[colors.tab_bar.new_tab_hover]", f'bg_color = "{k.p_h}"', f'fg_color = "{k.tx}"', "",
             "[metadata]", f'name = "{k.name}"', 'author = "unyxed"', ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- Neovim
# (Neovim highlight group, Zed capture). Neovim's tree-sitter captures use the same names as
# Zed's in most places and fall back on dot boundaries like Zed does, so each group simply takes
# the color Zed gives the matching capture.
NVIM_TS = [
    ("@variable", "variable"), ("@variable.builtin", "variable.special"), ("@variable.parameter", "variable.parameter"),
    ("@variable.parameter.builtin", "variable.special"), ("@variable.member", "property"),
    ("@constant", "constant"), ("@constant.builtin", "constant.builtin"), ("@constant.macro", "constant"),
    ("@module", "namespace"), ("@module.builtin", "namespace"), ("@label", "label"),
    ("@string", "string"), ("@string.documentation", "string"), ("@string.regexp", "string.regex"),
    ("@string.escape", "string.escape"), ("@string.special", "string.special"),
    ("@string.special.symbol", "string.special.symbol"), ("@string.special.url", "link_uri"),
    ("@string.special.path", "string.special"), ("@character", "string"), ("@character.special", "string.escape"),
    ("@boolean", "boolean"), ("@number", "number"), ("@number.float", "number"),
    ("@type", "type"), ("@type.builtin", "type.builtin"), ("@type.definition", "type"),
    ("@attribute", "attribute"), ("@attribute.builtin", "attribute"), ("@property", "property"),
    ("@function", "function"), ("@function.builtin", "function.builtin"), ("@function.call", "function"),
    ("@function.macro", "function"), ("@function.method", "function"), ("@function.method.call", "function"),
    ("@constructor", "constructor"), ("@operator", "operator"),
    ("@keyword", "keyword"), ("@keyword.directive", "preproc"), ("@keyword.directive.define", "preproc"),
    ("@keyword.import", "keyword"), ("@keyword.operator", "keyword"),
    ("@punctuation", "punctuation"), ("@punctuation.delimiter", "punctuation.delimiter"),
    ("@punctuation.bracket", "punctuation.bracket"), ("@punctuation.special", "punctuation.special"),
    ("@comment", "comment"), ("@comment.documentation", "comment.doc"),
    ("@markup.strong", "emphasis.strong"), ("@markup.italic", "emphasis"), ("@markup.heading", "title"),
    ("@markup.quote", "comment"), ("@markup.math", "text.literal"), ("@markup.link", "link_text"),
    ("@markup.link.label", "link_text"), ("@markup.link.url", "link_uri"), ("@markup.raw", "text.literal"),
    ("@markup.list", "punctuation.list_marker"), ("@diff.plus", "diff.plus"), ("@diff.minus", "diff.minus"),
    ("@diff.delta", "diff.delta"), ("@tag", "tag"), ("@tag.builtin", "tag"), ("@tag.attribute", "attribute"),
    ("@tag.delimiter", "punctuation.bracket"),
    # LSP semantic tokens
    ("@lsp.type.namespace", "namespace"), ("@lsp.type.type", "type"), ("@lsp.type.class", "type"),
    ("@lsp.type.struct", "type"), ("@lsp.type.interface", "type"), ("@lsp.type.typeParameter", "type"),
    ("@lsp.type.builtinType", "type.builtin"), ("@lsp.type.enum", "enum"), ("@lsp.type.enumMember", "variant"),
    ("@lsp.type.parameter", "variable.parameter"), ("@lsp.type.variable", "variable"),
    ("@lsp.type.property", "property"), ("@lsp.type.function", "function"), ("@lsp.type.method", "function"),
    ("@lsp.type.macro", "constant"), ("@lsp.type.decorator", "attribute"), ("@lsp.type.keyword", "keyword"),
    ("@lsp.type.string", "string"), ("@lsp.type.number", "number"), ("@lsp.type.boolean", "boolean"),
    ("@lsp.type.regexp", "string.regex"), ("@lsp.type.operator", "operator"), ("@lsp.type.label", "label"),
    ("@lsp.type.selfKeyword", "variable.special"), ("@lsp.type.selfParameter", "variable.special"),
    ("@lsp.type.lifetime", "lifetime"), ("@lsp.typemod.function.defaultLibrary", "function.builtin"),
    # classic Vim groups (plugins and languages without tree-sitter)
    ("Comment", "comment"), ("Constant", "constant"), ("String", "string"), ("Character", "string"),
    ("Number", "number"), ("Boolean", "boolean"), ("Float", "number"), ("Identifier", "variable"),
    ("Function", "function"), ("Statement", "keyword"), ("Conditional", "keyword"), ("Repeat", "keyword"),
    ("Label", "label"), ("Operator", "operator"), ("Keyword", "keyword"), ("Exception", "keyword"),
    ("PreProc", "preproc"), ("Include", "keyword"), ("Define", "preproc"), ("Macro", "constant"),
    ("PreCondit", "preproc"), ("Type", "type"), ("StorageClass", "keyword"), ("Structure", "keyword"),
    ("Typedef", "keyword"), ("Special", "variable.special"), ("SpecialChar", "string.escape"), ("Tag", "tag"),
    ("Delimiter", "punctuation.delimiter"), ("SpecialComment", "comment.doc"), ("Debug", "keyword"),
]


def nvim_groups(k):
    g = {}
    for group, cap in NVIM_TS:
        st = k.tok(cap)
        d = {"fg": st["color"][:7]}
        if st.get("font_style") == "italic" or cap in ("emphasis", "comment"):
            d["italic"] = True
        if st.get("font_weight") or cap == "emphasis.strong":
            d["bold"] = True
        g[group] = d
    g["@markup.link.url"]["underline"] = True
    g["@string.special.url"]["underline"] = True
    g["@markup.strikethrough"] = {"strikethrough": True}
    g["@markup.underline"] = {"underline": True}
    g["@markup.list.checked"] = {"fg": k.green}
    g["@markup.list.unchecked"] = {"fg": k.cm}
    g["@comment.error"] = {"fg": k.on(k.red), "bg": k.red, "bold": True}
    g["@comment.warning"] = {"fg": k.on(k.yellow), "bg": k.yellow, "bold": True}
    g["@comment.todo"] = {"fg": k.on(k.blue), "bg": k.blue, "bold": True}
    g["@comment.note"] = {"fg": k.on(k.aqua), "bg": k.aqua, "bold": True}
    g["@lsp.type.comment"] = {}  # let tree-sitter keep TODO/NOTE highlights inside comments
    bg, panel, tx, cm, sel, acc = k.bg, k.panel, k.tx, k.cm, k.sel, k.accent
    sel_flat = B.over(bg, B.alpha(acc, .25))
    diag = {"Error": k.red, "Warn": k.yellow, "Info": k.blue, "Hint": k.aqua, "Ok": k.green}
    ui = {
        "Normal": {"fg": tx, "bg": bg}, "NormalNC": {"fg": tx, "bg": bg}, "NormalFloat": {"fg": tx, "bg": k.elev},
        "FloatBorder": {"fg": k.border, "bg": k.elev}, "FloatTitle": {"fg": acc, "bg": k.elev, "bold": True},
        "FloatFooter": {"fg": k.muted, "bg": k.elev},
        "ColorColumn": {"bg": k.line_bg}, "Conceal": {"fg": cm}, "Cursor": {"fg": k.on(acc), "bg": acc},
        "lCursor": {"link": "Cursor"}, "CursorIM": {"link": "Cursor"}, "TermCursor": {"link": "Cursor"},
        "CursorLine": {"bg": k.line_bg}, "CursorColumn": {"bg": k.line_bg},
        "CursorLineNr": {"fg": tx, "bold": True}, "LineNr": {"fg": k.linenum},
        "LineNrAbove": {"fg": k.linenum}, "LineNrBelow": {"fg": k.linenum},
        "SignColumn": {"bg": bg}, "FoldColumn": {"fg": cm, "bg": bg},
        "Folded": {"fg": k.muted, "bg": B.over(bg, B.alpha(k.blue, .08))},
        "Directory": {"fg": k.blue}, "Title": {"fg": k.tcol("title"), "bold": True},
        "EndOfBuffer": {"fg": bg}, "NonText": {"fg": k.guide_a}, "Whitespace": {"fg": k.guide_a},
        "SpecialKey": {"fg": k.guide_a},
        "Visual": {"bg": sel_flat}, "VisualNOS": {"bg": sel_flat},
        "Search": {"bg": B.over(bg, B.alpha(k.blue, .3)), "fg": tx},
        "IncSearch": {"bg": k.orange, "fg": k.on(k.orange)}, "CurSearch": {"bg": k.orange, "fg": k.on(k.orange)},
        "Substitute": {"bg": k.red, "fg": k.on(k.red)}, "MatchParen": {"bg": B.over(bg, B.alpha(acc, .25)), "bold": True},
        "Pmenu": {"fg": tx, "bg": k.elev}, "PmenuSel": {"bg": sel, "bold": True},
        "PmenuKind": {"fg": k.blue, "bg": k.elev}, "PmenuKindSel": {"fg": k.blue, "bg": sel},
        "PmenuExtra": {"fg": k.muted, "bg": k.elev}, "PmenuExtraSel": {"fg": k.muted, "bg": sel},
        "PmenuSbar": {"bg": k.elev}, "PmenuThumb": {"bg": k.el_a}, "PmenuMatch": {"fg": k.ink(acc, k.elev), "bold": True},
        "PmenuMatchSel": {"fg": k.ink(acc, sel), "bold": True},
        "StatusLine": {"fg": k.muted, "bg": panel}, "StatusLineNC": {"fg": cm, "bg": panel},
        "TabLine": {"fg": k.muted, "bg": panel}, "TabLineFill": {"bg": panel}, "TabLineSel": {"fg": tx, "bg": bg, "bold": True},
        "WinBar": {"fg": k.muted, "bg": bg}, "WinBarNC": {"fg": cm, "bg": bg},
        "WinSeparator": {"fg": k.border}, "VertSplit": {"fg": k.border},
        "WildMenu": {"bg": sel}, "QuickFixLine": {"bg": sel, "bold": True},
        "ErrorMsg": {"fg": k.red}, "WarningMsg": {"fg": k.yellow}, "MoreMsg": {"fg": k.green},
        "ModeMsg": {"fg": tx, "bold": True}, "Question": {"fg": k.blue}, "MsgArea": {"fg": tx},
        "Error": {"fg": k.red}, "Todo": {"fg": k.on(k.yellow), "bg": k.yellow, "bold": True},
        "Underlined": {"underline": True}, "Ignore": {"fg": cm},
        "DiffAdd": {"bg": B.over(bg, B.alpha(k.green, .18))}, "DiffDelete": {"bg": B.over(bg, B.alpha(k.red, .18))},
        "DiffChange": {"bg": B.over(bg, B.alpha(k.blue, .12))}, "DiffText": {"bg": B.over(bg, B.alpha(k.blue, .3))},
        "Added": {"fg": k.green}, "Removed": {"fg": k.red}, "Changed": {"fg": k.yellow},
        "SpellBad": {"sp": k.red, "undercurl": True}, "SpellCap": {"sp": k.yellow, "undercurl": True},
        "SpellLocal": {"sp": k.blue, "undercurl": True}, "SpellRare": {"sp": k.purple, "undercurl": True},
        "LspReferenceText": {"bg": B.over(bg, B.alpha(k.blue, .15))},
        "LspReferenceRead": {"bg": B.over(bg, B.alpha(k.blue, .15))},
        "LspReferenceWrite": {"bg": B.over(bg, B.alpha(acc, .2))},
        "LspInlayHint": {"fg": k.ink(cm, k.el_bg, floor=k.r["ansi_dim"]), "bg": k.el_bg},
        "LspCodeLens": {"fg": cm}, "LspSignatureActiveParameter": {"fg": acc, "bold": True},
        "LspInfoBorder": {"link": "FloatBorder"},
        # plugins LazyVim ships
        "GitSignsAdd": {"fg": k.green}, "GitSignsChange": {"fg": k.yellow}, "GitSignsDelete": {"fg": k.red},
        "GitSignsCurrentLineBlame": {"fg": cm, "italic": True},
        "MiniIconsAzure": {"fg": k.blue}, "MiniIconsBlue": {"fg": k.blue}, "MiniIconsCyan": {"fg": k.aqua},
        "MiniIconsGreen": {"fg": k.green}, "MiniIconsGrey": {"fg": k.muted}, "MiniIconsOrange": {"fg": k.orange},
        "MiniIconsPurple": {"fg": k.purple}, "MiniIconsRed": {"fg": k.red}, "MiniIconsYellow": {"fg": k.yellow},
        "WhichKey": {"fg": k.aqua}, "WhichKeyGroup": {"fg": k.blue}, "WhichKeyDesc": {"fg": tx},
        "WhichKeySeparator": {"fg": cm}, "WhichKeyNormal": {"bg": k.elev}, "WhichKeyBorder": {"link": "FloatBorder"},
        "WhichKeyValue": {"fg": cm},
        "FlashLabel": {"fg": k.on(acc), "bg": acc, "bold": True}, "FlashMatch": {"fg": k.blue},
        "FlashCurrent": {"fg": k.orange}, "FlashBackdrop": {"fg": cm},
        "SnacksIndent": {"fg": k.guide}, "SnacksIndentScope": {"fg": k.guide_a},
        "SnacksPickerMatch": {"fg": k.ink(acc, k.elev), "bold": True}, "SnacksPickerDir": {"fg": cm},
        "SnacksPickerBorder": {"link": "FloatBorder"}, "SnacksPickerTitle": {"link": "FloatTitle"},
        "SnacksDashboardHeader": {"fg": acc}, "SnacksDashboardKey": {"fg": k.orange},
        "SnacksDashboardDesc": {"fg": tx}, "SnacksDashboardIcon": {"fg": k.blue},
        "SnacksDashboardFooter": {"fg": cm}, "SnacksDashboardSpecial": {"fg": k.purple},
        "SnacksNotifierBorderInfo": {"fg": k.blue}, "SnacksNotifierBorderWarn": {"fg": k.yellow},
        "SnacksNotifierBorderError": {"fg": k.red}, "SnacksNotifierTitleInfo": {"fg": k.blue},
        "SnacksNotifierTitleWarn": {"fg": k.yellow}, "SnacksNotifierTitleError": {"fg": k.red},
        "BlinkCmpMenu": {"link": "Pmenu"}, "BlinkCmpMenuBorder": {"link": "FloatBorder"},
        "BlinkCmpMenuSelection": {"link": "PmenuSel"}, "BlinkCmpLabelMatch": {"fg": k.ink(acc, k.elev), "bold": True},
        "BlinkCmpKind": {"fg": k.blue}, "BlinkCmpDoc": {"link": "NormalFloat"},
        "BlinkCmpDocBorder": {"link": "FloatBorder"}, "BlinkCmpGhostText": {"fg": k.tcol("predictive")},
        "NeoTreeNormal": {"fg": tx, "bg": panel}, "NeoTreeNormalNC": {"fg": tx, "bg": panel},
        "NeoTreeDirectoryName": {"fg": tx}, "NeoTreeDirectoryIcon": {"fg": k.blue}, "NeoTreeRootName": {"fg": acc, "bold": True},
        "NeoTreeGitAdded": {"fg": k.green}, "NeoTreeGitModified": {"fg": k.yellow}, "NeoTreeGitDeleted": {"fg": k.red},
        "NeoTreeGitUntracked": {"fg": k.green}, "NeoTreeGitIgnored": {"fg": cm}, "NeoTreeGitConflict": {"fg": k.orange},
        "NeoTreeIndentMarker": {"fg": k.border}, "NeoTreeWinSeparator": {"fg": panel, "bg": panel},
        "TelescopeBorder": {"link": "FloatBorder"}, "TelescopeMatching": {"fg": acc, "bold": True},
        "TelescopeSelection": {"bg": sel}, "TelescopeNormal": {"link": "NormalFloat"},
        "TroubleNormal": {"fg": tx, "bg": panel}, "TroubleNormalNC": {"fg": tx, "bg": panel},
        "NoiceCmdlinePopupBorder": {"link": "FloatBorder"}, "NoiceCmdlineIcon": {"fg": acc},
        "BufferLineFill": {"bg": panel},
        "TodoBgTODO": {"fg": k.on(k.blue), "bg": k.blue, "bold": True}, "TodoFgTODO": {"fg": k.blue},
        "TodoBgFIX": {"fg": k.on(k.red), "bg": k.red, "bold": True}, "TodoFgFIX": {"fg": k.red},
        "TodoBgWARN": {"fg": k.on(k.yellow), "bg": k.yellow, "bold": True}, "TodoFgWARN": {"fg": k.yellow},
        "TodoBgNOTE": {"fg": k.on(k.aqua), "bg": k.aqua, "bold": True}, "TodoFgNOTE": {"fg": k.aqua},
        "TodoBgHACK": {"fg": k.on(k.orange), "bg": k.orange, "bold": True}, "TodoFgHACK": {"fg": k.orange},
        "TodoBgPERF": {"fg": k.on(k.purple), "bg": k.purple, "bold": True}, "TodoFgPERF": {"fg": k.purple},
    }
    for name, col in diag.items():
        ui[f"Diagnostic{name}"] = {"fg": col}
        ui[f"DiagnosticVirtualText{name}"] = {"fg": col, "bg": B.mix(bg, col, .1)}
        ui[f"DiagnosticUnderline{name}"] = {"sp": col, "undercurl": True}
        ui[f"DiagnosticSign{name}"] = {"fg": col}
        ui[f"DiagnosticFloating{name}"] = {"fg": col}
    ui["DiagnosticUnnecessary"] = {"fg": cm}
    ui["DiagnosticDeprecated"] = {"sp": cm, "strikethrough": True}
    g.update(ui)
    return g


def lua_value(d):
    parts = []
    for key in ("link", "fg", "bg", "sp"):
        if key in d:
            parts.append(f'{key} = "{d[key][:7] if key != "link" else d[key]}"')
    for key in ("bold", "italic", "underline", "undercurl", "strikethrough"):
        if d.get(key):
            parts.append(f"{key} = true")
    return "{ " + ", ".join(parts) + " }" if parts else "{}"


def neovim(k, need):
    g = nvim_groups(k)
    lines = [f"-- {k.name} for Neovim. Generated by tools/build.py from palettes.json; do not edit.",
             'vim.cmd("highlight clear")', 'if vim.fn.exists("syntax_on") == 1 then vim.cmd("syntax reset") end',
             f'vim.o.background = "{"dark" if k.dark else "light"}"', f'vim.g.colors_name = "{k.slug}"', "",
             "local groups = {"]
    for name in g:
        key = name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else f'["{name}"]'
        lines.append(f"  {key} = {lua_value(g[name])},")
    lines += ["}", "for name, val in pairs(groups) do", "  vim.api.nvim_set_hl(0, name, val)", "end", ""]
    for i, n in enumerate(B.ANSI_NAMES):
        lines.append(f'vim.g.terminal_color_{i} = "{k.ansi[n]}"')
    for i, n in enumerate(B.ANSI_NAMES):
        lines.append(f'vim.g.terminal_color_{i + 8} = "{k.ansi["bright_" + n]}"')
    for fg, bgc, what in [(k.tx, B.over(k.bg, B.alpha(k.accent, .25)), "visual selection"),
                          (k.tx, k.sel, "menu selection"), (k.ink(k.accent, k.sel), k.sel, "menu match on selection"),
                          (k.muted, k.panel, "status line"), (k.on(k.orange), k.orange, "current search match")]:
        need(k.name, fg, bgc, k.r["ansi"], f"neovim text on {what}")
    return "\n".join(lines) + "\n"


def lualine(k, need):
    def mode(col):
        return (f'{{ a = {{ fg = "{k.on(col)}", bg = "{col}", gui = "bold" }}, '
                f'b = {{ fg = "{k.tx}", bg = "{k.el_a}" }}, c = {{ fg = "{k.muted}", bg = "{k.panel}" }} }}')
    for col in (k.accent, k.green, k.purple, k.red, k.yellow):
        need(k.name, k.on(col), col, k.r["ansi"], "lualine mode label")
    need(k.name, k.tx, k.el_a, k.r["ansi"], "lualine section text")
    return "\n".join([
        f"-- {k.name} for lualine (LazyVim's status line). Generated by tools/build.py; do not edit.",
        "return {", f"  normal = {mode(k.accent)},", f"  insert = {mode(k.green)},", f"  visual = {mode(k.purple)},",
        f"  replace = {mode(k.red)},", f"  command = {mode(k.yellow)},", f"  terminal = {mode(k.aqua)},",
        f'  inactive = {{ a = {{ fg = "{k.cm}", bg = "{k.panel}" }}, b = {{ fg = "{k.cm}", bg = "{k.panel}" }}, '
        f'c = {{ fg = "{k.cm}", bg = "{k.panel}" }} }},', "}", ""])


# ---------------------------------------------------------------- fzf and PowerShell
def fzf(k, need):
    hl, hl_sel = k.ink(k.accent, k.bg), k.ink(k.accent, k.sel)
    spec = (f"fg:{k.tx},bg:{k.bg},hl:{hl},fg+:{k.tx},bg+:{k.sel},hl+:{hl_sel},info:{k.muted},"
            f"border:{k.border},separator:{k.border},scrollbar:{k.el_a},label:{k.muted},query:{k.tx},"
            f"prompt:{k.accent},pointer:{k.accent},marker:{k.green},spinner:{k.aqua},header:{k.blue},"
            f"gutter:{k.bg},preview-fg:{k.tx},preview-bg:{k.bg}")
    need(k.name, hl_sel, k.sel, k.r["ansi"], "fzf match on the current line")
    return spec


def fzf_files(pkg, data):
    sh = [f"# {pkg['name']} for fzf (bash/zsh). Generated by tools/build.py; do not edit.",
          "# Uncomment the theme you want, or source this file after setting UNYXED_THEME=<slug>.",
          'case "${UNYXED_THEME:-}" in']
    ps = [f"# {pkg['name']} for fzf (PowerShell). Generated by tools/build.py; do not edit.",
          "# In $PROFILE:  $env:UNYXED_THEME = '<slug>'; . '<this repo>\\ports\\fzf\\fzf.ps1'",
          "$unyxedFzf = @{"]
    for _, v in B.variants(data):
        k = Ctx(v)
        spec = fzf(k, lambda *a: None)
        sh.append(f'  {k.slug}) export FZF_DEFAULT_OPTS="$FZF_DEFAULT_OPTS --color={spec}" ;;')
        ps.append(f"  '{k.slug}' = '--color={spec}'")
    sh += ["esac", ""]
    ps += ["}", "if ($env:UNYXED_THEME -and $unyxedFzf.ContainsKey($env:UNYXED_THEME)) {",
           "  $env:FZF_DEFAULT_OPTS = (\"$env:FZF_DEFAULT_OPTS \" + $unyxedFzf[$env:UNYXED_THEME]).Trim()", "}", ""]
    return "\n".join(sh), "\n".join(ps)


def psreadline(k, need):
    def esc(col, italic=False, back=False):
        r, g, b = B.h2r(col)
        return f"$e[{'3;' if italic else ''}{48 if back else 38};2;{r};{g};{b}m"
    pred = k.ink(k.cm, k.bg, floor=k.r["ansi_dim"])
    rows = [("Default", esc(k.tx)), ("Command", esc(k.tcol("function"))), ("Keyword", esc(k.tcol("keyword"))),
            ("String", esc(k.tcol("string"))), ("Number", esc(k.tcol("number"))), ("Type", esc(k.tcol("type"))),
            ("Operator", esc(k.tcol("operator"))), ("Variable", esc(k.tcol("variable.special"))),
            ("Member", esc(k.tcol("property"))), ("Parameter", esc(k.tcol("attribute"))),
            ("Comment", esc(k.cm, italic=True)), ("ContinuationPrompt", esc(k.cm)),
            ("Emphasis", esc(k.accent)), ("Error", esc(k.red)), ("Selection", esc(k.sel, back=True)),
            ("InlinePrediction", esc(pred, italic=True)), ("ListPrediction", esc(k.yellow)),
            ("ListPredictionSelected", esc(k.sel, back=True)), ("ListPredictionTooltip", esc(k.cm))]
    return "\n".join([f"# {k.name} for PSReadLine (PowerShell typing colors). Generated by tools/build.py; do not edit.",
                      "# Dot-source it from $PROFILE:  . '<this repo>\\ports\\powershell\\" + k.slug + ".ps1'",
                      "# Needs PSReadLine 2.1+ (Windows PowerShell 5.1 and PowerShell 7 both work).",
                      "$e = [char]27", "Set-PSReadLineOption -Colors @{"]
                     + [f'  {n} = "{s}"' for n, s in rows] + ["}", ""])


# ---------------------------------------------------------------- browsers
def chrome_manifest(k, need):
    on_frame = k.tx
    colors = {
        "frame": k.panel, "frame_inactive": k.panel, "frame_incognito": B.mix(k.panel, k.purple, .12),
        "frame_incognito_inactive": B.mix(k.panel, k.purple, .12), "background_tab": k.panel,
        "background_tab_inactive": k.panel, "background_tab_incognito": k.panel,
        "toolbar": k.bg, "tab_text": k.tx, "tab_background_text": k.muted, "tab_background_text_inactive": k.cm,
        "bookmark_text": k.tx, "toolbar_text": k.tx, "toolbar_button_icon": k.icon,
        "omnibox_background": k.el_bg, "omnibox_text": k.tx,
        "ntp_background": k.bg, "ntp_text": k.tx, "ntp_link": k.blue, "ntp_header": k.panel,
        "button_background": k.el_bg,
    }
    need(k.name, k.muted, k.panel, k.r["ansi"], "chrome background tab text")
    need(k.name, on_frame, k.panel, k.r["ansi"], "chrome tab text")
    return {"manifest_version": 3, "name": k.name, "version": version(),
            "description": f"{k.name}, generated from palettes.json.",
            "theme": {"colors": {n: rgb(c) for n, c in colors.items()},
                      "properties": {"ntp_background_alignment": "bottom"}}}


def firefox_manifest(pkg, k, need):
    acc = k.accent
    colors = {
        "frame": k.panel, "frame_inactive": k.panel, "tab_background_text": k.muted, "tab_text": k.tx,
        "tab_selected": k.bg, "tab_line": acc, "tab_loading": acc, "tab_background_separator": k.border,
        "toolbar": k.bg, "toolbar_text": k.tx, "toolbar_field": k.el_bg, "toolbar_field_text": k.tx,
        "toolbar_field_border": k.bvar, "toolbar_field_focus": k.el_bg, "toolbar_field_text_focus": k.tx,
        "toolbar_field_border_focus": acc, "toolbar_field_highlight": B.over(k.el_bg, k.fade(acc, .35, k.el_bg)),
        "toolbar_field_highlight_text": k.tx, "toolbar_top_separator": k.panel, "toolbar_bottom_separator": k.bvar,
        "toolbar_vertical_separator": k.border, "popup": k.elev, "popup_text": k.tx, "popup_border": k.border,
        "popup_highlight": k.sel, "popup_highlight_text": k.tx, "sidebar": k.panel, "sidebar_text": k.tx,
        "sidebar_border": k.bvar, "sidebar_highlight": k.sel, "sidebar_highlight_text": k.tx,
        "button_background_hover": k.el_h, "button_background_active": k.el_a, "icons": k.icon,
        "icons_attention": acc, "ntp_background": k.bg, "ntp_text": k.tx, "ntp_card_background": k.elev,
    }
    need(k.name, k.tx, colors["toolbar_field_highlight"], k.r["ansi"], "firefox address bar selection")
    need(k.name, k.muted, k.panel, k.r["ansi"], "firefox background tab text")
    return {"manifest_version": 2, "name": k.name, "version": version(),
            "description": f"{k.name}, generated from palettes.json.",
            "browser_specific_settings": {"gecko": {"id": f"{k.slug}@{pkg['id']}",
                                                      "data_collection_permissions": {"required": ["none"]}}},
            "theme": {"colors": colors, "properties": {"color_scheme": "dark" if k.dark else "light",
                                                        "content_color_scheme": "dark" if k.dark else "light"}}}


def media(dark):
    return f"@media (prefers-color-scheme: {'dark' if dark else 'light'})"


def zen_chrome(title, ks):
    out = [f"/* {title} for Zen Browser (userChrome.css). Generated by tools/build.py from palettes.json; do not edit. */", ""]
    for k in ks:
        acc = k.accent
        out += [f"/* {k.name} */", media(k.dark) + " {", "  :root {",
                f"    --zen-colors-primary: {k.el_h} !important;", f"    --zen-primary-color: {acc} !important;",
                f"    --zen-colors-secondary: {k.el_h} !important;", f"    --zen-colors-tertiary: {k.panel} !important;",
                f"    --zen-colors-border: {acc} !important;", f"    --toolbarbutton-icon-fill: {k.icon} !important;",
                f"    --lwt-text-color: {k.tx} !important;", f"    --toolbar-field-color: {k.tx} !important;",
                f"    --tab-selected-textcolor: {k.tx} !important;", f"    --toolbar-field-focus-color: {k.tx} !important;",
                f"    --toolbar-color: {k.tx} !important;", f"    --newtab-text-primary-color: {k.tx} !important;",
                f"    --arrowpanel-color: {k.tx} !important;", f"    --arrowpanel-background: {k.elev} !important;",
                f"    --sidebar-text-color: {k.tx} !important;", f"    --lwt-sidebar-text-color: {k.tx} !important;",
                f"    --lwt-sidebar-background-color: {k.panel} !important;",
                f"    --toolbar-bgcolor: {k.el_h} !important;", f"    --newtab-background-color: {k.bg} !important;",
                f"    --zen-themed-toolbar-bg: {k.panel} !important;",
                f"    --zen-main-browser-background: {k.panel} !important;",
                f"    --toolbox-bgcolor-inactive: {k.panel} !important;",
                f"    --tab-selected-bgcolor: {k.bg} !important;", f"    --focus-outline-color: {acc} !important;",
                "  }",
                f"  #TabsToolbar, hbox#titlebar, #zen-appcontent-navbar-container {{ background-color: {k.panel} !important; }}",
                f"  .urlbar-background, #zen-workspaces-button, .sidebar-placesTree {{ background-color: {k.bg} !important; }}",
                f"  .urlbarView-url {{ color: {k.ink(k.blue, k.elev)} !important; }}",
                f"  .content-shortcuts {{ background-color: {k.bg} !important; border-color: {acc} !important; }}",
                f"  #zen-media-controls-toolbar #zen-media-progress-bar::-moz-range-track {{ background: {k.el_h} !important; }}",
                f"  ::selection {{ background-color: {k.sel} !important; color: {k.tx} !important; }}"]
        for ident, col in [("blue", k.blue), ("turquoise", k.aqua), ("green", k.green), ("yellow", k.yellow),
                           ("orange", k.orange), ("red", k.red), ("pink", B.mix(k.purple, k.red, .4)),
                           ("purple", k.purple)]:
            out.append(f"  .identity-color-{ident} {{ --identity-tab-color: {col} !important; "
                       f"--identity-icon-color: {col} !important; }}")
        out += ["}", ""]
    return "\n".join(out)


def zen_content(title, ks):
    out = [f"/* {title} for Zen Browser (userContent.css): new tab and about: pages. Generated by tools/build.py; do not edit. */", ""]
    for k in ks:
        acc = k.accent
        out += [f"/* {k.name} */", media(k.dark) + " {", '  @-moz-document url-prefix("about:") {', "    :root {",
                f"      --in-content-page-color: {k.tx} !important;", f"      --in-content-page-background: {k.bg} !important;",
                f"      --in-content-text-color: {k.tx} !important;", f"      --in-content-box-background: {k.elev} !important;",
                f"      --color-accent-primary: {acc} !important;",
                f"      --color-accent-primary-hover: {B.mix(acc, k.tx, .15)} !important;",
                f"      --color-accent-primary-active: {B.mix(acc, k.tx, .25)} !important;",
                f"      --link-color: {k.ink(k.blue, k.bg)} !important;", f"      --zen-primary-color: {acc} !important;",
                f"      --zen-colors-primary: {k.el_h} !important;", f"      --zen-colors-tertiary: {k.panel} !important;",
                f"      background-color: {k.bg} !important;", "    }", "  }",
                '  @-moz-document url("about:newtab"), url("about:home") {', "    :root {",
                f"      --newtab-background-color: {k.bg} !important;",
                f"      --newtab-background-color-secondary: {k.elev} !important;",
                f"      --newtab-element-hover-color: {k.el_h} !important;",
                f"      --newtab-text-primary-color: {k.tx} !important;", f"      --newtab-wordmark-color: {k.tx} !important;",
                f"      --newtab-primary-action-background: {acc} !important;", "    }",
                f"    .card-outer:is(:hover, :focus, .active):not(.placeholder) .card-title {{ color: {k.ink(acc, k.bg)} !important; }}",
                "  }", "}", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- GitHub (Stylus userstyle)
def github_vars(k):
    bg, panel, tx, cm, acc = k.bg, k.panel, k.tx, k.cm, k.accent
    A = lambda col, a: B.alpha(col, a)
    on_acc, on_green, on_red = k.on(acc), k.on(k.green), k.on(k.red)
    crust = B.mix(panel, "#000000", .12) if k.dark else B.mix(panel, tx, .06)
    muted = k.ink(k.muted, bg, panel, crust)
    link = k.ink(k.blue, bg, panel)
    v = {
        "--fgColor-default": tx, "--fgColor-muted": muted, "--fgColor-onEmphasis": on_acc, "--fgColor-onInverse": bg,
        "--fgColor-white": tx, "--fgColor-black": bg, "--fgColor-disabled": k.dis, "--fgColor-link": link,
        "--fgColor-neutral": muted, "--fgColor-accent": link, "--fgColor-success": k.ink(k.green, bg, panel),
        "--fgColor-attention": k.ink(k.yellow, bg, panel), "--fgColor-severe": k.ink(k.orange, bg, panel),
        "--fgColor-danger": k.ink(k.red, bg, panel), "--fgColor-open": k.ink(k.green, bg, panel),
        "--fgColor-closed": k.ink(k.red, bg, panel), "--fgColor-done": k.ink(k.purple, bg, panel),
        "--fgColor-sponsors": k.ink(B.mix(k.purple, k.red, .4), bg, panel), "--fgColor-upsell": k.ink(k.purple, bg, panel),
        "--bgColor-default": bg, "--bgColor-muted": panel, "--bgColor-inset": crust, "--bgColor-emphasis": k.muted,
        "--bgColor-inverse": tx, "--bgColor-white": bg, "--bgColor-black": crust, "--bgColor-disabled": k.el_bg,
        "--bgColor-transparent": "#00000000", "--bgColor-neutral-muted": A(cm, .2), "--bgColor-neutral-emphasis": cm,
        "--bgColor-accent-muted": A(acc, .15), "--bgColor-accent-emphasis": acc,
        "--bgColor-success-muted": A(k.green, .15), "--bgColor-success-emphasis": k.green,
        "--bgColor-attention-muted": A(k.yellow, .15), "--bgColor-attention-emphasis": k.yellow,
        "--bgColor-severe-muted": A(k.orange, .15), "--bgColor-severe-emphasis": k.orange,
        "--bgColor-danger-muted": A(k.red, .15), "--bgColor-danger-emphasis": k.red,
        "--bgColor-open-muted": A(k.green, .15), "--bgColor-open-emphasis": k.green,
        "--bgColor-closed-muted": A(k.red, .15), "--bgColor-closed-emphasis": k.red,
        "--bgColor-done-muted": A(k.purple, .15), "--bgColor-done-emphasis": k.purple,
        "--bgColor-sponsors-muted": A(k.purple, .12), "--bgColor-sponsors-emphasis": B.mix(k.purple, k.red, .4),
        "--bgColor-upsell-muted": A(k.purple, .12), "--bgColor-upsell-emphasis": k.purple,
        "--borderColor-default": k.border, "--borderColor-muted": k.bvar, "--borderColor-emphasis": B.mix(panel, tx, .3),
        "--borderColor-disabled": k.bvar, "--borderColor-transparent": "#00000000",
        "--borderColor-translucent": A(tx, .15), "--borderColor-neutral-muted": k.bvar,
        "--borderColor-neutral-emphasis": cm, "--borderColor-accent-muted": A(acc, .5),
        "--borderColor-accent-emphasis": acc, "--borderColor-success-muted": A(k.green, .5),
        "--borderColor-success-emphasis": k.green, "--borderColor-attention-muted": A(k.yellow, .5),
        "--borderColor-attention-emphasis": k.yellow, "--borderColor-severe-muted": A(k.orange, .5),
        "--borderColor-severe-emphasis": k.orange, "--borderColor-danger-muted": A(k.red, .5),
        "--borderColor-danger-emphasis": k.red, "--borderColor-open-muted": A(k.green, .5),
        "--borderColor-open-emphasis": k.green, "--borderColor-closed-muted": A(k.red, .5),
        "--borderColor-closed-emphasis": k.red, "--borderColor-done-muted": A(k.purple, .5),
        "--borderColor-done-emphasis": k.purple,
        "--focus-outlineColor": acc, "--selection-bgColor": A(acc, .3), "--overlay-bgColor": k.elev,
        "--overlay-borderColor": k.border, "--overlay-backdrop-bgColor": A(crust, .6),
        "--header-bgColor": crust, "--header-fgColor-default": tx, "--header-fgColor-logo": tx,
        "--header-borderColor-divider": k.border, "--headerSearch-bgColor": panel, "--headerSearch-borderColor": k.border,
        "--page-header-bgColor": crust, "--menu-bgColor-active": k.el_h, "--sideNav-bgColor-selected": k.el_h,
        "--underlineNav-borderColor-active": acc, "--underlineNav-borderColor-hover": k.border,
        "--underlineNav-iconColor-rest": muted, "--timelineBadge-bgColor": panel, "--avatar-borderColor": k.bvar,
        "--tooltip-bgColor": tx, "--tooltip-fgColor": bg, "--treeViewItem-leadingVisual-iconColor-rest": muted,
        "--control-bgColor-rest": k.el_bg, "--control-bgColor-hover": k.el_h, "--control-bgColor-active": k.el_a,
        "--control-bgColor-disabled": k.el_bg, "--control-bgColor-selected": k.el_h, "--control-fgColor-rest": tx,
        "--control-fgColor-placeholder": cm, "--control-fgColor-disabled": k.dis, "--control-borderColor-rest": k.border,
        "--control-borderColor-emphasis": B.mix(panel, tx, .3), "--control-borderColor-selected": acc,
        "--control-borderColor-success": k.green, "--control-borderColor-danger": k.red,
        "--control-borderColor-warning": k.yellow, "--control-iconColor-rest": muted,
        "--control-transparent-bgColor-hover": A(tx, .08), "--control-transparent-bgColor-active": A(tx, .12),
        "--control-transparent-bgColor-selected": A(tx, .1), "--control-checked-bgColor-rest": acc,
        "--control-checked-bgColor-hover": B.mix(acc, tx, .1), "--control-checked-bgColor-active": B.mix(acc, tx, .15),
        "--control-checked-fgColor-rest": on_acc, "--control-checked-borderColor-rest": acc,
        "--controlTrack-bgColor-rest": k.el_h, "--controlTrack-bgColor-hover": k.el_a, "--controlKnob-bgColor-rest": bg,
        "--controlKnob-bgColor-checked": on_acc, "--controlKnob-borderColor-rest": k.border,
        "--button-default-fgColor-rest": tx, "--button-default-bgColor-rest": k.el_bg,
        "--button-default-bgColor-hover": k.el_h, "--button-default-bgColor-active": k.el_a,
        "--button-default-bgColor-selected": k.el_a, "--button-default-borderColor-rest": k.border,
        "--button-default-borderColor-hover": k.border, "--button-default-borderColor-active": k.border,
        "--button-primary-fgColor-rest": on_green, "--button-primary-iconColor-rest": on_green,
        "--button-primary-bgColor-rest": k.green, "--button-primary-bgColor-hover": B.mix(k.green, tx, .1),
        "--button-primary-bgColor-active": B.mix(k.green, tx, .15), "--button-primary-borderColor-rest": k.green,
        "--button-primary-bgColor-disabled": A(k.green, .5), "--button-primary-fgColor-disabled": A(on_green, .7),
        "--button-invisible-fgColor-rest": tx, "--button-invisible-iconColor-rest": muted,
        "--button-invisible-bgColor-hover": A(tx, .08), "--button-invisible-bgColor-active": A(tx, .12),
        "--button-outline-fgColor-rest": link, "--button-outline-bgColor-hover": k.el_h,
        "--button-outline-bgColor-active": acc, "--button-outline-fgColor-active": on_acc,
        "--button-danger-fgColor-rest": k.ink(k.red, k.el_bg), "--button-danger-iconColor-rest": k.ink(k.red, k.el_bg),
        "--button-danger-bgColor-rest": k.el_bg, "--button-danger-fgColor-hover": on_red,
        "--button-danger-iconColor-hover": on_red, "--button-danger-bgColor-hover": k.red,
        "--button-danger-bgColor-active": B.mix(k.red, tx, .1), "--button-danger-borderColor-hover": k.red,
        "--button-star-iconColor": k.yellow, "--buttonCounter-default-bgColor-rest": k.el_a,
        "--reactionButton-selected-bgColor-rest": A(acc, .2), "--reactionButton-selected-bgColor-hover": A(acc, .3),
        "--reactionButton-selected-fgColor-rest": k.ink(acc, B.over(bg, A(acc, .2))),
        "--highlight-neutral-bgColor": A(k.yellow, .3),
        "--diffBlob-additionLine-bgColor": A(k.green, .15), "--diffBlob-additionWord-bgColor": k.fade(k.green, .35),
        "--diffBlob-additionNum-bgColor": k.fade(k.green, .3), "--diffBlob-additionNum-fgColor": tx,
        "--diffBlob-additionWord-fgColor": tx, "--diffBlob-deletionLine-bgColor": A(k.red, .15),
        "--diffBlob-deletionWord-bgColor": k.fade(k.red, .35), "--diffBlob-deletionNum-bgColor": k.fade(k.red, .3),
        "--diffBlob-deletionNum-fgColor": tx, "--diffBlob-deletionWord-fgColor": tx,
        "--diffBlob-hunkLine-bgColor": A(k.blue, .15), "--diffBlob-hunkNum-bgColor-rest": A(k.blue, .3),
        "--diffBlob-hunkNum-bgColor-hover": A(k.blue, .5), "--diffBlob-emptyLine-bgColor": panel,
        "--diffBlob-emptyNum-bgColor": panel, "--diffBlob-expander-iconColor": muted,
        "--codeMirror-fgColor": tx, "--codeMirror-bgColor": bg, "--codeMirror-gutters-bgColor": bg,
        "--codeMirror-lineNumber-fgColor": k.linenum, "--codeMirror-cursor-fgColor": acc,
        "--codeMirror-selection-bgColor": A(acc, .25), "--codeMirror-activeline-bgColor": k.line_bg,
        "--codeMirror-matchingBracket-fgColor": tx, "--codeMirror-lines-bgColor": bg,
        "--codeMirror-syntax-fgColor-comment": cm, "--codeMirror-syntax-fgColor-constant": k.tcol("number"),
        "--codeMirror-syntax-fgColor-entity": k.tcol("function"), "--codeMirror-syntax-fgColor-keyword": k.tcol("keyword"),
        "--codeMirror-syntax-fgColor-storage": k.tcol("keyword"), "--codeMirror-syntax-fgColor-string": k.tcol("string"),
        "--codeMirror-syntax-fgColor-support": k.tcol("type"), "--codeMirror-syntax-fgColor-variable": k.tcol("variable.special"),
        # code highlighting: GitHub's prettylights tokens, mapped to the Gruvbox groups
        "--color-prettylights-syntax-comment": cm, "--color-prettylights-syntax-constant": k.tcol("number"),
        "--color-prettylights-syntax-constant-other-reference-link": k.tcol("link_uri"),
        "--color-prettylights-syntax-entity": k.tcol("function"), "--color-prettylights-syntax-entity-tag": k.tcol("tag"),
        "--color-prettylights-syntax-keyword": k.tcol("keyword"), "--color-prettylights-syntax-string": k.tcol("string"),
        "--color-prettylights-syntax-string-regexp": k.tcol("string.regex"),
        "--color-prettylights-syntax-variable": k.tcol("variable.special"),
        "--color-prettylights-syntax-storage-modifier-import": tx,
        "--color-prettylights-syntax-sublimelinter-gutter-mark": cm,
        "--color-prettylights-syntax-brackethighlighter-angle": k.tcol("punctuation.bracket"),
        "--color-prettylights-syntax-brackethighlighter-unmatched": k.red,
        "--color-prettylights-syntax-carriage-return-text": tx, "--color-prettylights-syntax-carriage-return-bg": A(k.red, .3),
        "--color-prettylights-syntax-invalid-illegal-text": k.red, "--color-prettylights-syntax-invalid-illegal-bg": A(k.red, .15),
        "--color-prettylights-syntax-markup-heading": k.tcol("title"), "--color-prettylights-syntax-markup-list": tx,
        "--color-prettylights-syntax-markup-italic": k.tcol("emphasis"), "--color-prettylights-syntax-markup-bold": k.tcol("emphasis.strong"),
        "--color-prettylights-syntax-markup-deleted-text": tx, "--color-prettylights-syntax-markup-deleted-bg": A(k.red, .25),
        "--color-prettylights-syntax-markup-inserted-text": tx, "--color-prettylights-syntax-markup-inserted-bg": A(k.green, .25),
        "--color-prettylights-syntax-markup-changed-text": tx, "--color-prettylights-syntax-markup-changed-bg": A(k.yellow, .25),
        "--color-prettylights-syntax-markup-ignored-text": tx, "--color-prettylights-syntax-markup-ignored-bg": A(k.blue, .25),
        "--color-prettylights-syntax-meta-diff-range": k.tcol("attribute"),
        # contribution graph in the accent
        "--contribution-default-bgColor-0": k.el_bg, "--contribution-default-bgColor-1": A(acc, .35),
        "--contribution-default-bgColor-2": A(acc, .55), "--contribution-default-bgColor-3": A(acc, .78),
        "--contribution-default-bgColor-4": acc, "--contribution-default-borderColor-0": "#00000000",
        "--color-calendar-graph-day-bg": k.el_bg, "--color-calendar-graph-day-L1-bg": A(acc, .35),
        "--color-calendar-graph-day-L2-bg": A(acc, .55), "--color-calendar-graph-day-L3-bg": A(acc, .78),
        "--color-calendar-graph-day-L4-bg": acc,
        "--color-user-mention-fg": k.ink(acc, B.over(bg, A(acc, .2))), "--color-user-mention-bg": A(acc, .2),
        # docs.github.com and older pages
        "--color-fg-default": tx, "--color-fg-muted": muted, "--color-canvas-default": bg, "--color-canvas-subtle": panel,
        "--color-border-default": k.border, "--color-accent-fg": link,
    }
    for i, n in enumerate(B.ANSI_NAMES):
        name = {"black": "black", "white": "white"}.get(n, n)
        v[f"--color-ansi-{name}"] = k.ansi[n]
        v[f"--color-ansi-{name}-bright"] = k.ansi["bright_" + n]
    v["--color-ansi-gray"] = k.ansi["bright_black"]
    return v


def github_userstyle(pkg, title, ks, need):
    head = ["/* ==UserStyle==", f"@name           GitHub - {title}", f"@namespace      {pkg['id']}/github",
            f"@version        {version()}", f"@description    {title} ({pkg['name']}) for GitHub. "
            "Generated by tools/build.py from palettes.json; do not edit.", f"@author         {pkg['author']}",
            "==/UserStyle== */", "",
            '@-moz-document domain("github.com"), domain("gist.github.com"), domain("docs.github.com") {']
    body = []
    for k in ks:
        mode = "dark" if k.dark else "light"
        decl = "\n".join(f"    {n}: {c} !important;" for n, c in github_vars(k).items())
        extra = (f"    accent-color: {k.accent};\n    color-scheme: {mode};")
        body += [f"  /* {k.name}: GitHub in {mode} mode, or auto mode while the system is {mode} */",
                 f'  [data-color-mode="{mode}"] {{', decl, extra, "  }",
                 f"  {media(k.dark)} {{", '    [data-color-mode="auto"] {',
                 "\n".join("  " + line for line in decl.split("\n")), "  " + extra.replace("\n", "\n  "), "    }", "  }",
                 f'  [data-color-mode="{mode}"] ::selection {{ background-color: {B.alpha(k.accent, .3)} !important; }}', ""]
        gv = github_vars(k)
        for fg, b, what in [(gv["--fgColor-muted"], k.panel, "muted text on the muted background"),
                            (gv["--fgColor-link"], k.panel, "links on the muted background"),
                            (gv["--button-primary-fgColor-rest"], k.green, "primary button text"),
                            (gv["--button-danger-fgColor-hover"], k.red, "danger button text"),
                            (gv["--fgColor-onEmphasis"], k.accent, "text on accent badges"),
                            (k.tx, B.over(k.bg, gv["--diffBlob-additionWord-bgColor"]), "added words in diffs"),
                            (k.tx, B.over(k.bg, gv["--diffBlob-deletionWord-bgColor"]), "removed words in diffs"),
                            (gv["--color-user-mention-fg"], B.over(k.bg, gv["--color-user-mention-bg"]), "mentions")]:
            need(k.name, fg, b, k.r["ansi"], f"github {what}")
    return "\n".join(head + body + ["}", ""])


# ---------------------------------------------------------------- Discord (Vencord / BetterDiscord)
def discord_vars(k):
    bg, panel, tx, cm, acc = k.bg, k.panel, k.tx, k.cm, k.accent
    crust = B.mix(panel, "#000000", .12) if k.dark else B.mix(panel, tx, .06)
    A = lambda col, a: B.alpha(col, a)
    on_acc = k.on(acc)
    muted = k.ink(k.muted, bg, panel, crust)
    link = k.ink(k.blue, bg, panel)
    v = {}
    # brand scale: 500 is the accent, lower numbers lighter, higher darker
    for n in (100, 130, 160, 200, 230, 260, 300, 330, 360, 400, 430, 460, 500, 530, 560, 600, 630, 660, 700,
              730, 760, 800, 830, 860, 900):
        t = (500 - n) / 500 * .9
        v[f"--brand-{n}"] = B.mix(acc, "#FFFFFF", t) if t > 0 else B.mix(acc, "#000000", -t)
    for a in range(5, 100, 5):
        v[f"--brand-{a:02d}a"] = A(acc, a / 100)
    v.update({
        "--text-default": tx, "--text-normal": tx, "--text-strong": tx, "--header-primary": tx,
        "--header-secondary": muted, "--text-muted": muted, "--text-subtle": muted, "--text-link": link,
        "--text-brand": k.ink(acc, bg, panel), "--text-feedback-positive": k.ink(k.green, bg, panel),
        "--text-feedback-critical": k.ink(k.red, bg, panel), "--text-feedback-warning": k.ink(k.yellow, bg, panel),
        "--text-feedback-info": link, "--channels-default": muted, "--channel-icon": muted,
        "--channel-text-area-placeholder": cm, "--channeltextarea-background": panel,
        "--icon-default": tx, "--icon-strong": tx, "--icon-subtle": muted, "--icon-muted": muted,
        "--interactive-normal": muted, "--interactive-hover": tx, "--interactive-active": tx, "--interactive-muted": k.dis,
        "--interactive-icon-default": muted, "--interactive-icon-hover": tx, "--interactive-icon-active": tx,
        "--interactive-text-default": muted, "--interactive-text-hover": tx, "--interactive-text-active": tx,
        "--interactive-background-hover": A(tx, .07), "--interactive-background-selected": A(tx, .11),
        "--interactive-background-active": A(tx, .14),
        "--background-primary": bg, "--background-secondary": panel, "--background-secondary-alt": crust,
        "--background-tertiary": crust, "--background-floating": k.elev, "--background-accent": k.el_a,
        "--background-base-lowest": crust, "--background-base-lower": panel, "--background-base-low": panel,
        "--background-surface-high": bg, "--background-surface-higher": k.elev, "--background-surface-highest": k.el_h,
        "--background-gradient-highest": panel, "--bg-surface-raised": panel, "--app-frame-background": crust,
        "--__header-bar-background": panel, "--home-background": bg, "--chat-background": bg,
        "--chat-background-default": bg, "--chat-border": crust, "--chat-text-muted": muted,
        "--modal-background": bg, "--modal-footer-background": panel, "--card-background-default": k.elev,
        "--custom-channel-members-bg": panel, "--user-profile-overlay-background": panel,
        "--user-profile-overlay-background-hover": k.el_h,
        "--background-mod-muted": A(tx, .04), "--background-mod-subtle": A(tx, .07),
        "--background-mod-normal": A(tx, .1), "--background-mod-strong": A(tx, .16),
        "--background-modifier-hover": A(tx, .06), "--background-modifier-active": A(tx, .1),
        "--background-modifier-selected": A(tx, .12), "--background-modifier-accent": A(tx, .12),
        "--border-subtle": k.bvar, "--border-muted": k.bvar, "--border-normal": k.border, "--border-strong": k.border,
        "--input-background": k.el_bg, "--input-background-default": k.el_bg, "--input-text-default": tx,
        "--input-placeholder-text-default": cm, "--input-border-default": k.border,
        "--scrollbar-thin-thumb": A(tx, .2), "--scrollbar-thin-track": "transparent",
        "--scrollbar-auto-thumb": A(tx, .2), "--scrollbar-auto-track": "transparent",
        "--scrollbar-auto-scrollbar-color-thumb": A(tx, .2), "--scrollbar-auto-scrollbar-color-track": "transparent",
        "--control-brand-foreground": k.ink(acc, bg), "--control-brand-foreground-new": k.ink(acc, bg),
        "--control-primary-background-default": acc, "--control-primary-background-hover": B.mix(acc, tx, .12),
        "--control-primary-background-active": B.mix(acc, tx, .2), "--control-primary-text-default": on_acc,
        "--control-primary-text-hover": on_acc, "--control-primary-text-active": on_acc,
        "--control-secondary-background-default": k.el_h, "--control-secondary-background-hover": k.el_a,
        "--control-secondary-background-active": k.el_a, "--control-secondary-text-default": tx,
        "--control-secondary-text-hover": tx, "--control-secondary-border-default": k.border,
        "--control-critical-primary-background-default": k.red,
        "--control-critical-primary-background-hover": B.mix(k.red, tx, .12),
        "--control-critical-primary-background-active": B.mix(k.red, tx, .2),
        "--control-critical-primary-text-default": k.on(k.red), "--control-critical-primary-text-hover": k.on(k.red),
        "--control-connected-background-default": k.green, "--control-connected-background-hover": B.mix(k.green, tx, .12),
        "--control-connected-background-active": B.mix(k.green, tx, .2),
        "--button-filled-brand-background": acc, "--button-filled-brand-background-hover": B.mix(acc, tx, .12),
        "--button-filled-brand-text": on_acc, "--button-secondary-background": k.el_h,
        "--button-secondary-background-hover": k.el_a, "--button-danger-background": k.red,
        "--button-positive-background": k.green,
        "--mention-foreground": k.ink(acc, B.over(bg, A(acc, .3))), "--mention-background": A(acc, .3),
        "--message-reacted-background-default": A(acc, .25), "--message-reacted-text-default": k.ink(acc, B.over(bg, A(acc, .25))),
        "--message-mentioned-background-default": A(k.yellow, .12), "--message-mentioned-background-hover": A(k.yellow, .16),
        "--message-background-hover": A(tx, .04), "--message-highlight-background-default": A(acc, .08),
        "--message-highlight-background-hover": A(acc, .12), "--background-message-hover": A(tx, .04),
        "--background-mentioned": A(k.yellow, .12), "--background-mentioned-hover": A(k.yellow, .16),
        "--info-warning-foreground": k.yellow, "--info-danger-foreground": k.red, "--info-positive-foreground": k.green,
        "--background-code": panel, "--textbox-markdown-syntax": cm,
        "--spoiler-revealed-background": k.el_h, "--spoiler-hidden-background": k.el_a,
        "--focus-primary": acc, "--__adaptive-focus-ring-color": acc, "--logo-primary": tx,
        "--status-positive": k.green, "--status-positive-background": k.green, "--status-positive-text": k.on(k.green),
        "--status-warning": k.yellow, "--status-warning-background": k.yellow, "--status-warning-text": k.on(k.yellow),
        "--status-danger": k.red, "--status-danger-background": k.red, "--status-danger-text": k.on(k.red),
        "--background-feedback-positive": A(k.green, .15), "--background-feedback-warning": A(k.yellow, .15),
        "--background-feedback-critical": A(k.red, .15), "--background-feedback-info": A(k.blue, .15),
        "--background-feedback-notification": k.red, "--badge-notification-background": k.red,
        "--badge-text-brand": on_acc, "--icon-feedback-positive": k.green, "--icon-feedback-warning": k.yellow,
        "--icon-feedback-critical": k.red, "--icon-feedback-info": k.blue, "--icon-voice-muted": k.red,
        "--text-status-online": k.green, "--text-status-idle": k.yellow, "--text-status-dnd": k.red,
        "--text-status-offline": muted, "--icon-status-online": k.green, "--icon-status-idle": k.yellow,
        "--icon-status-dnd": k.red, "--icon-status-offline": cm, "--status-online": k.green, "--status-idle": k.yellow,
        "--status-dnd": k.red, "--status-offline": cm,
        "--notice-background-critical": k.red, "--notice-background-info": k.blue,
        "--notice-background-positive": k.green, "--notice-background-warning": k.yellow,
        "--notice-text-critical": k.on(k.red), "--notice-text-info": k.on(k.blue),
        "--notice-text-positive": k.on(k.green), "--notice-text-warning": k.on(k.yellow),
        "--blurple-50": acc, "--blurple-60": B.mix(acc, "#000000", .1), "--green-360": k.green, "--green-300": k.green,
        "--yellow-360": k.yellow, "--yellow-300": k.yellow, "--red-400": k.red, "--red-430": k.red, "--red-500": k.red,
        "--blue-500": k.blue, "--blue-530": k.blue, "--twitch": k.purple, "--spotify": k.green,
        "--guild-boosting-pink": B.mix(k.purple, k.red, .4), "--guild-boosting-purple": k.purple,
        "--guild-boosting-blue": k.blue,
    })
    return v


DISCORD_CODE = [  # highlight.js classes in Discord code blocks -> Zed captures
    ("hljs-comment, .hljs-quote", "comment"), ("hljs-keyword, .hljs-selector-tag, .hljs-meta .hljs-keyword", "keyword"),
    ("hljs-built_in", "function.builtin"), ("hljs-title.function_, .hljs-title, .hljs-section", "function"),
    ("hljs-string, .hljs-meta .hljs-string", "string"), ("hljs-type, .hljs-title.class_", "type"),
    ("hljs-number", "number"), ("hljs-literal", "boolean"), ("hljs-symbol", "string.special.symbol"),
    ("hljs-regexp", "string.regex"), ("hljs-attr, .hljs-attribute", "property"), ("hljs-variable.language_", "variable.special"),
    ("hljs-variable, .hljs-template-variable, .hljs-params", "variable"), ("hljs-name", "tag"),
    ("hljs-meta", "preproc"), ("hljs-operator", "operator"), ("hljs-punctuation", "punctuation"),
    ("hljs-link", "link_uri"), ("hljs-bullet", "punctuation.list_marker"), ("hljs-emphasis", "emphasis"),
    ("hljs-strong", "emphasis.strong"), ("hljs-selector-class, .hljs-selector-id", "selector"),
    ("hljs-selector-pseudo", "selector.pseudo"), ("hljs-addition", "diff.plus"), ("hljs-deletion", "diff.minus"),
    ("hljs-subst", "variable"), ("hljs-doctag", "comment.doc"),
]


def discord_theme(pkg, title, ks, need):
    out = ["/**", f" * @name {title}", f" * @author {pkg['author']}", f" * @version {version()}",
           f" * @description {title} ({pkg['name']}). Generated by tools/build.py from palettes.json; do not edit.",
           " */", ""]
    for k in ks:
        mode = "dark" if k.dark else "light"
        sel = f".theme-{mode}, .visual-refresh.theme-{mode}, .visual-refresh .theme-{mode}"
        out.append(f"/* {k.name} */")
        out.append(sel + " {")
        for n, c in discord_vars(k).items():
            out.append(f"  {n}: {c} !important;")
        out.append("}")
        for cls, cap in DISCORD_CODE:
            st = k.tok(cap)
            extra = ";font-style:italic" if cap in ("comment", "emphasis") else (
                ";font-weight:700" if cap == "emphasis.strong" else "")
            # code blocks sit on --background-code (the panel): nudge each color until readable there
            col = k.ink(st["color"][:7], k.panel, floor=k.r["ansi_dim"] if cap == "comment" else k.r["ansi"])
            out.append(f".theme-{mode} .{cls} {{ color: {col} !important{extra} }}")
        out.append(f".theme-{mode} .hljs {{ background: {k.panel} !important; color: {k.tx} !important; }}")
        out.append(f".theme-{mode} ::selection {{ background-color: {B.alpha(k.accent, .35)}; }}")
        out.append("")
        dv = discord_vars(k)
        for fg, b, what in [(dv["--text-muted"], B.mix(k.panel, "#000000", .12) if k.dark else B.mix(k.panel, k.tx, .06),
                             "muted text on the server list"),
                            (dv["--text-muted"], k.panel, "channel names"), (dv["--text-link"], k.bg, "links"),
                            (dv["--control-primary-text-default"], k.accent, "button text"),
                            (dv["--mention-foreground"], B.over(k.bg, dv["--mention-background"]), "mentions"),
                            (dv["--status-warning-text"], k.yellow, "warning labels"),
                            (dv["--notice-text-info"], k.blue, "info banners")]:
            need(k.name, fg, b, k.r["ansi"], f"discord {what}")
    return "\n".join(out)


# ---------------------------------------------------------------- Dark Reader
def darkreader_selection(k, need):
    """Dark Reader draws selected text white on a selection whose HSL lightness is under 50%, else
    black. Pick our selection color and nudge it (same hue) until that text stays readable."""
    sel = k.sel
    for _ in range(100):
        r, g, b = (x / 255 for x in B.h2r(sel))
        light = (max(r, g, b) + min(r, g, b)) / 2 >= 0.5
        fg = "#000000" if light else "#FFFFFF"
        if B.contrast(fg, sel) >= k.r["ansi"]:
            break
        sel = B.mix(sel, "#000000" if not light else "#FFFFFF", .04)
    need(k.name, fg, sel, k.r["ansi"], "dark reader selected text")
    return sel


def darkreader(k, schemes, need):
    """Dark Reader settings to import (Settings > Advanced > Import Settings). Only `theme` is set, and
    Dark Reader merges an import into the current settings key by key, so site lists stay as they are.
    The dark and light scheme colors come from the family's Dark and Light variants, so Dark Reader's
    dark/light switch moves between the pair; `mode` starts on this variant's own appearance. A family
    with no variant for a scheme (IDK's Mid Tones are all light) gets this variant inverted for it."""
    theme = {"mode": 1 if k.dark else 0, "brightness": 100, "contrast": 100, "grayscale": 0, "sepia": 0,
             "useFont": False, "fontFamily": "Segoe UI", "textStroke": 0, "engine": "dynamicTheme",
             "stylesheet": ""}
    for app in ("dark", "light"):
        o = schemes.get(app)
        back, text = (o.bg, o.tx) if o else (k.tx, k.bg)
        need(k.name, text, back, k.r["text"], f"dark reader {app} scheme text")
        theme[f"{app}SchemeBackgroundColor"], theme[f"{app}SchemeTextColor"] = back.lower(), text.lower()
    theme.update({"scrollbarColor": "auto", "selectionColor": darkreader_selection(k, need).lower(),
                  "styleSystemControls": False, "lightColorScheme": "Default", "darkColorScheme": "Default",
                  "immediateModify": False})
    return {"theme": theme}


# ---------------------------------------------------------------- write everything
def build_all(pkg, data, write):
    """Generate every port. `write(relpath, text_or_bytes)` stores a file. Returns (problems, counts)."""
    need = Need()
    counts = {}
    vs = [v for _, v in B.variants(data)]
    ks = {v["name"]: Ctx(v) for v in vs}
    ident = pkg["id"]

    def each(port, ext, gen, slug_of=lambda k: k.slug):
        for v in vs:
            k = ks[v["name"]]
            write(f"ports/{port}/{slug_of(k)}{ext}", gen(k, need))
        counts[port] = len(vs)

    # terminals
    each("ghostty", "", ghostty, slug_of=lambda k: k.name)
    each("kitty", ".conf", kitty)
    each("alacritty", ".toml", alacritty)
    each("wezterm", ".toml", wezterm)

    # VS Code: an extension folder plus a ready-to-install .vsix (the .vsix is not committed)
    themes = {}
    for v in vs:
        k = ks[v["name"]]
        themes[f"{k.slug}.json"] = json.dumps(vscode_theme(k, need), indent=2) + "\n"
    manifest = vscode_package(pkg, data)
    write("ports/vscode/package.json", json.dumps(manifest, indent=2) + "\n")
    for name, text in themes.items():
        write(f"ports/vscode/themes/{name}", text)
    write(f"ports/vscode/{ident}.vsix", vsix(pkg, manifest, themes))
    counts["vscode"] = len(vs)

    # Neovim: colors/ and lua/lualine/themes/ at the repo root, so lazy.nvim can load the repo itself
    for v in vs:
        k = ks[v["name"]]
        write(f"colors/{k.slug}.lua", neovim(k, need))
        write(f"lua/lualine/themes/{k.slug}.lua", lualine(k, need))
    counts["neovim"] = len(vs)

    # bat / delta / Sublime share the TextMate theme
    each("tmtheme", ".tmTheme", tmtheme, slug_of=lambda k: k.name)
    write(f"ports/delta/{ident}.gitconfig", delta_gitconfig(pkg, data))
    sh, ps = fzf_files(pkg, data)
    for v in vs:
        fzf(ks[v["name"]], need)
    write("ports/fzf/fzf.sh", sh)
    write("ports/fzf/fzf.ps1", ps)
    each("powershell", ".ps1", psreadline)

    # browsers
    for v in vs:
        k = ks[v["name"]]
        write(f"ports/chrome/{k.slug}/manifest.json", json.dumps(chrome_manifest(k, need), indent=2) + "\n")
        fx = json.dumps(firefox_manifest(pkg, k, need), indent=2) + "\n"
        write(f"ports/firefox/{k.slug}/manifest.json", fx)
        write(f"ports/firefox/{k.slug}.xpi", zip_bytes({"manifest.json": fx}))
    counts["chrome"] = counts["firefox"] = len(vs)
    n_units = 0
    for fam in data["families"]:
        for name, title, uvs in units(fam):
            group = [ks[v["name"]] for v in uvs]
            write(f"ports/zen/{name}/userChrome.css", zen_chrome(title, group))
            write(f"ports/zen/{name}/userContent.css", zen_content(title, group))
            write(f"ports/github/{ident}-{name}.user.css", github_userstyle(pkg, title, group, need))
            write(f"ports/discord/{ident}-{name}.theme.css", discord_theme(pkg, title, group, need))
            n_units += 1
    counts["zen"] = counts["github"] = counts["discord"] = n_units
    for fam in data["families"]:
        schemes = {}
        for v in fam["variants"]:
            schemes.setdefault(v["appearance"], ks[v["name"]])
        for v in fam["variants"]:
            k = ks[v["name"]]
            own = {**schemes, v["appearance"]: k}
            write(f"ports/darkreader/{k.slug}.json", json.dumps(darkreader(k, own, need), indent=2) + "\n")
    counts["darkreader"] = len(vs)
    return need.problems, counts


# Generated paths (relative to the repo root) that build.py owns and may delete before writing.
OWNED_DIRS = ["ports/ghostty", "ports/kitty", "ports/alacritty", "ports/wezterm", "ports/vscode", "colors",
              "lua/lualine/themes", "ports/tmtheme", "ports/delta", "ports/fzf", "ports/powershell",
              "ports/chrome", "ports/firefox", "ports/zen", "ports/github", "ports/discord",
              "ports/darkreader"]


def syntax_check(files):
    """Parse every generated file whose format Python can read, so a port never ships broken."""
    probs = []
    try:
        import tomllib
    except ImportError:  # Python < 3.11: skip the TOML check
        tomllib = None
    for path, data in files.items():
        text = data if isinstance(data, str) else None
        try:
            if path.endswith(".json"):
                json.loads(text)
            elif path.endswith(".toml") and tomllib:
                tomllib.loads(text)
            elif path.endswith(".tmTheme"):
                plistlib.loads(text.encode("utf-8"))
            elif path.endswith((".vsix", ".xpi")):
                zipfile.ZipFile(io.BytesIO(data)).testzip()
            elif path.endswith(".css") or path.endswith(".lua"):
                pairs = "{}" if path.endswith(".css") else "{}"
                if text.count(pairs[0]) != text.count(pairs[1]):
                    raise ValueError("unbalanced braces")
        except Exception as e:  # noqa: BLE001 - report any parse failure as a build error
            probs.append(f"generated {path} does not parse: {e}")
    return probs
