#!/usr/bin/env python3
"""Set bypass state for /noskill command. Called during preprocessing."""
import json
import os
from pathlib import Path

# Debug logging
debug_log = Path('/tmp/hook-debug.log')
def log(msg):
    if os.environ.get('SKILL_HOOK_DEBUG') == '1':
        existing = debug_log.read_text() if debug_log.exists() else ''
        debug_log.write_text(existing + f'[noskill-cmd] {msg}\n')

log('=== /NOSKILL COMMAND PREPROCESSING ===')

state_file = Path('/tmp/skill-session-state.json')
existing = {}
if state_file.exists():
    try:
        existing = json.loads(state_file.read_text())
        log(f'Read existing state: prompt_count={existing.get("prompt_count", 0)}')
    except Exception as e:
        log(f'Could not read existing state: {e}')

state = {
    'skills_suggested': [],
    'selected_skill': None,
    'ask_question_answered': False,
    'no_skill_needed': True,
    'activated': [],
    'prompt_count': existing.get('prompt_count', 0) + 1
}

Path('/tmp/skill-session-state.tmp').write_text(json.dumps(state, indent=2))
Path('/tmp/skill-session-state.tmp').rename(state_file)
log(f'Set bypass state: no_skill_needed=True, prompt_count={state["prompt_count"]}')
log('=== /NOSKILL COMMAND COMPLETE ===')
