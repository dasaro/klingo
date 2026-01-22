% Variant: if consonant then even
card(c1,vowel).
card(c2,consonant).
card(c3,even).
card(c4,odd).

1 { h1; -h1 } 1.
1 { h2; -h2 } 1.
ok_rule :- h1, h2.

flip(C) :- ok_rule, card(C,consonant).
flip(C) :- ok_rule, card(C,odd).

#show flip/1.
#show ok_rule/0.
