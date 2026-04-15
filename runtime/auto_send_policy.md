# Auto Send Policy V1

This clone is configured for auto-send, but only when all gates pass.

## Must-pass conditions

1. classifier confidence >= 0.8
2. contact mode is not `uncertain`
3. message is not in a sensitive category
4. output length is within limit
5. reply tone matches chosen mode

## Sensitive categories that must not auto-send

- money / transfer / borrowing
- conflict escalation
- breakup / relationship rupture
- serious work decisions
- legal / contract style commitment
- threats / insults / emotionally extreme messages

If triggered:

- do not send
- log as `blocked_sensitive`

## Low-confidence rule

If confidence < 0.8:

- do not send
- log as `blocked_low_confidence`

## Length rule

- if generated reply is abnormally long for the mode, do not auto-send
- prefer short natural messages

## Logging rule

Store per event:

- contact
- incoming message
- chosen mode
- confidence
- whether a subcard was loaded
- generated reply
- final result: sent / blocked
