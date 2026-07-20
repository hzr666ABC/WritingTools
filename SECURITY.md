# Security Policy

## Supported versions

Security fixes are provided for the latest release and the current default branch.
Older portable builds may not receive fixes.

## Reporting a vulnerability

Please do not open a public Issue for an unpatched vulnerability or include API
keys, selected text, prompts, configuration files, or diagnostic reports in a
public post. Use the repository's **Security → Report a vulnerability** flow to
open a private GitHub Security Advisory. Include reproduction steps and impact,
but replace all credentials and personal text with synthetic examples.

If private vulnerability reporting is unavailable on a fork, contact the
maintainer privately before publishing details. You should receive an initial
acknowledgement within seven days. Disclosure timing will be coordinated after a
fix is available.

## Security and privacy model

- Writing Tools has no telemetry. Text is sent only when the user invokes a
  preset, and only to the configured Gemini, OpenAI-compatible, or Ollama
  endpoint.
- Remote OpenAI-compatible endpoints that receive API keys must use HTTPS.
  Plain HTTP is accepted only for loopback development endpoints. Ollama may use
  local HTTP because it does not use an API key in this application.
- On Windows, credentials and history text are protected with DPAPI for the
  current Windows user. On Linux/macOS, AES-256-GCM uses an owner-only key under
  the user's data directory. This protects against accidental config/history
  disclosure; it does not protect against malware running as the same OS user.
- Local encrypted history can be disabled and cleared from Settings. Metadata
  such as time, provider, model, and preset name is stored in plaintext.
- Imported preset packs are untrusted data. They are size- and schema-limited,
  cannot configure providers, and never import or export API credentials.
- The safe-apply preview is a trust boundary: AI output is never executed as
  code by Writing Tools, and users can compare, copy, apply, undo, or restore.

## Release checks

Run these commands before publishing:

```powershell
python scripts/security_check.py --history
python -m pip_audit -r Windows_and_Linux/requirements-lock.txt
python -m unittest discover -s Windows_and_Linux/tests -v
```

Release archives must not contain `config.json`, `history.json`, logs, local
vault keys, private certificates, API keys, or user-specific paths.
