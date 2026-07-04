% Property: --bnm can produce depth-sensitive belief flips from axioms alone.
child(anne;martha;jane).
blonde(anne).
-blonde(jane).
looks_at(anne,martha).
looks_at(martha,jane).

answer_yes :- looks_at(X,Y), blonde(X), -blonde(Y).
-answer_yes :- not answer_yes.
answer_no  :- -answer_yes.

#show answer_yes/0.
#show -answer_yes/0.
#show answer_no/0.
#show blonde/1.
#show -blonde/1.
