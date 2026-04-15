# Manual Review Fallback V1

Even though the primary mode is auto-send, blocked replies should still be recoverable for human review.

When blocked:

1. save draft in logs
2. mark reason:
   - low confidence
   - sensitive category
   - abnormal length
   - missing route
3. allow later review and resend manually

This keeps the system from silently failing while still protecting against bad sends.
