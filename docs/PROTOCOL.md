# Experimental application protocol v2 — Japanese cues

Existing modified Celio 2.0.6 raw relay remains unchanged. This is an application payload over the existing multiplayer transport, not a new physical transport. Browser verifies firmware 2.0.6. Command endpoints OUT1/IN1, data OUT2/IN2; uint16 little endian. Raw mode4, master, GBA cable, timing7400. No reboot or flash.

Frame: A55A, (type<<8)|count, payload, negative sum(head+payload) modulo65536. Payload max29 words; packet max64 bytes.

- 22: transaction low16/high16, offset, total characters, up to25 Unicode BMP values. Total1..65. Chunks must be contiguous; exact duplicates tolerated. Unsupported glyphs rejected.
- 23 commit: transaction low/high, CRC16-CCITT(initialFFFF,poly1021) over little-endian words [idLow,idHigh,total,characters...]. Commit only after complete valid staging.
- 31 receipt: transaction low/high, same CRC. Emitted only after all80 scanlines are rendered. Repeats until replaced by a newer completed draw. A packet snapshots its ID/CRC to avoid mixing receipts.
- Heartbeat D302, old D301 detected as incompatible ROM. Keys B000|active bits0..9. Browser edge detection avoids repeated held buttons.

Web generates nonzero32bit transaction IDs, seeded randomly each page load; increments per send. Exact ID and CRC required for success. At most one send active. Receipts are not authentication. Message frame transfers suspend polling; ordinary poll C001 twice/80ms resumes afterwards. Confirmation timeout3s after USB transfers; no automatic message retry. Missing device traffic2.5s closes link. Old read loops are invalidated on close/reconnect.

ROM draws one scanline per main-loop iteration to return to serial polling frequently. Earlier v1 used a one-shot receipt, which was not observed despite user-confirmed text. Repetition addresses a plausible loss mode; actual cause and real hardware latency remain unverified. Host tests cannot establish ARM/SIO deadlines. Font render is13×5 characters at16px, including ASCII fixed width. Browser NFC normalization and coverage checks reject unsupported input.

Public cues are distributable; private overrides remain in browser memory only and are sent only to the explicitly selected device. They do not change font subsets or public files. Main preview masks private text; settings dialog must be closed before screen sharing.

References: [GBATEK multiplayer](https://mgba-emu.github.io/gbatek/#sio-multiplayer-mode), [Noto CJK](https://github.com/notofonts/noto-cjk). Neither is evidence of this new ROM working on hardware.
