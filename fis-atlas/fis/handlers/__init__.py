"""The handler shelf — small, single-purpose, op-coded units the core composes.

Each handler declares its op-code and a pure-ish function. The core loads only
what a rule asks for at that moment. Heavy engines (NLP classify, near-dup) get
ported in here as und/ and sim/ handlers.
"""
