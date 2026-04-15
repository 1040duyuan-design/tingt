# TingT Bad Case Buckets V1

Do not mix all bad cases together.

Split by entry type first:

1. invitation
2. check-in / checking-whereabouts
3. emotion
4. probing opener

Current priority:

- fix invitation first

Why:

- invitation replies are being misread as casual continuation
- this causes vague drift like `我想想`
- the result is neither a stance nor a real continuation

Rule:

- bucket first
- then apply the scene rule for that bucket
- do not let `de-qa` or generic continuation override the invitation rule
