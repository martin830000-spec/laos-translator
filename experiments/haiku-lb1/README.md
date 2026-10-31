# Haiku LB1 — offline source lexical-boundary candidate

FLORES-200 Korean/Lao human dev data was investigated for contextual retrieval.
The conservative CR1 search found no admissible references for the five existing
diagnostic messages. Its text domain is informational, not conversational. The
separate Lao-English dictionary also omits the everyday phone sense of a key
word. Neither corpus is promoted as a complete semantic oracle or paid candidate.

LB1 is the alternative implemented here: LaoNLP1.3.0 dictionary segmentation,
provided only as an approximate source boundary view beside the unchanged raw
message. It is not a translation example, dictionary gloss, fact summary or
target rewrite. All characters, whitespace, emoji and typo spellings must join
back exactly. Otherwise the hint is omitted and the original LA1 request remains.
Only Lao-input routes change. No transliteration to Thai is used; PyThaiNLP is
only LaoNLP's algorithm/Trie dependency with Lao dictionaries.

Unlike LA1 output-unit generation or LA2 forced target utterances, LB1 never
creates separate translation requests or changes target boundaries/display.
Model/disabled/LOW/2048/LA1 units remain frozen. BACK accepts only the final own
FIRST display, not its source units or original message. Every artifact stays.

This is a meaning-interpretation hypothesis, not a semantic fix demonstrated by
lossless tests. Dictionary boundaries can be wrong, and the model may still
misread compounds, conditions, actors or omit dates. Input tokens grow; API cost
and latency must be measured. New paid calls0. No live HTTP or trigger installed.

Install exact requirements. Run unittest discover -s experiments/haiku-lb1.
API: build_request(source,side,stage), prepare_back(first_response,side).
LaoNLP: https://github.com/wannaphong/LaoNLP (Phatthiyaphaibun,2022).
Tokenizer/library is Apache2.0; individual dictionaries have their own retained
notices (BSD-style, Apache2.0, CC-BY-SA3.0). Do not assume one license covers all.
