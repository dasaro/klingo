% Wason-like: if vowel then even
card(c1,vowel).
card(c2,consonant).
card(c3,even).
card(c4,odd).

% decision gate (both conditions required)
ok_rule :- h1, h2.

% training evidence pushes ok_rule true at higher depth
h1.
h2.

flip(C) :- ok_rule, card(C,vowel).
flip(C) :- ok_rule, card(C,odd).

#show flip/1.
#show ok_rule/0.
