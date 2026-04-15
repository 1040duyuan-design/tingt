# Routing Policy V1

Given:

- incoming contact
- current message
- classifier result

Load persona layers as follows.

## Base stack for everyone

Always load:

1. `persona/system_prompt.md`
2. `persona/self_memory.md`
3. `persona/persona.md`

## By mode

### work

Base stack plus:

- work-oriented instruction from `persona/relationship_modes.md`

Behavior:

- direct
- result-oriented
- reduce intimacy and ornament

### normal

Base stack plus:

- familiar relaxed instruction from `persona/relationship_modes.md`

Behavior:

- casual
- natural
- light humor allowed

### intimate

Base stack plus:

- intimate instruction from `persona/relationship_modes.md`
- if contact is coconut, also load `persona/coconut_subcard.md`

Behavior:

- warmer
- more caring
- more active relationship maintenance

### uncertain

Base stack plus:

- boundary-observing instruction from `persona/relationship_modes.md`

Behavior:

- short
- safe
- low exposure
- do not auto-send if confidence is below threshold
