# LB1C — zero-generation engineering candidate

Actual LB1 AB32 slots 4 and 14 omitted hints because LaoNLP 1.3.0 removed `/`
from a mixed spouse-label input. Frozen LB1 correctly fell back to exact LA1.
LB1C segments contiguous Lao Unicode-block runs only, and keeps every other
run verbatim. If even a Lao run is not lossless, it remains one unsplit run.
The whole original, model settings, LB1 wording and LA1 output contract stay
unchanged. No normalization, correction, translated examples or date/condition
rules are inserted. This is input coverage work, not a demonstrated semantic
solution for app92 or app67. Slash alternatives in FIRST remain visible; no
artifact cleanup is performed. Three contract tests and stored-output replay
do not establish translation quality. No live model transport is authorized.
