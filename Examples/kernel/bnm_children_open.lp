% Property: faithful children-puzzle encoding for --bnm.
% The #external declarations put Martha's hair colour into the question
% space: the grounder keeps the rule instances mentioning it, and the
% totality universe acquires the {blonde(martha); -blonde(martha)} pair.
% Expected behavior:
%   --bnm -k 0 --mode cautious : commits [b]answer_no, [b]-answer_yes,
%                                [b]-blonde(martha)  (the defaults answer "No")
%   --bnm -k 1 --mode cautious : answer_yes  (derived in every branch of the
%                                case split on Martha's hair colour)
child(anne;martha;jane).
blonde(anne).
-blonde(jane).
looks_at(anne,martha).
looks_at(martha,jane).

answer_yes :- looks_at(X,Y), blonde(X), -blonde(Y).
-answer_yes :- not answer_yes.
answer_no  :- -answer_yes.

#external blonde(martha).
#external -blonde(martha).

#show answer_yes/0.
#show -answer_yes/0.
#show answer_no/0.
#show blonde/1.
#show -blonde/1.
