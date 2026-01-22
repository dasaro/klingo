% learned defaults
% source: Experiments/wason/train.lp
% depth: 2
flip(c1) :- not -flip(c1).
flip(c2) :- not -flip(c2).
flip(c3) :- not -flip(c3).
flip(c4) :- not -flip(c4).
flip(consonant) :- not -flip(consonant).
flip(even) :- not -flip(even).
flip(odd) :- not -flip(odd).
flip(vowel) :- not -flip(vowel).
ok_rule :- not -ok_rule.
