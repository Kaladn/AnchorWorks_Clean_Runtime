# Non-CLI UI Removal Prep

Purpose: prepare AnchorWorks for a CLI-first/operator-surface cleanup without deleting UI files in this pass.

## Keep

CLI/operator surfaces:

```text
Anchorworks/src/AnchorWorks/cli.py
Anchorworks/src/AnchorWorks/cli_shell.py
Anchorworks/src/AnchorWorks/terminal_operator.py
```

Backend/API surfaces required for tests and SecureCore bridge:

```text
Anchorworks/src/AnchorWorks/app.py
```

## Candidate Non-CLI UI For Later Removal

Do not delete until approved:

```text
Anchorworks/UI/index.html
Anchorworks/UI/assets/app.js
Anchorworks/UI/assets/app.css
Anchorworks/UI/assets/icon.svg
Anchorworks/UI/assets/favicon.ico
Anchorworks/UI/manifest.webmanifest
```

## Store Path Lock

Active writable user stores:

```text
State/user/user_lexicon/anchors.json
State/user/user_counts/symbol_counts_binary/
State/user/chat_logs/
```

Canonical seed/reference stores:

```text
Canonical/
Structural/
State/symbol_counts_binary/
```

Bad code-folder runtime root:

```text
Anchorworks/State/
```

This root is ignored and rejected by `LexiconStore` when used as a data root.

## Removal Rule

```text
Remove non-CLI UI only after:
1. CLI tests pass.
2. API bridge tests pass.
3. SecureCore no longer references Anchorworks/UI.
4. No runtime data lives under Anchorworks/State.
```
