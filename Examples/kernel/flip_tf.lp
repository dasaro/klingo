% Property: direct T -> F polarity flip at k=0 -> k=1 under --bnm.
% The unique stable model is {a}, so a is presumed true at depth 0.
% But P + totality classically entails c (bivalence on b makes one of
% the two c-rules fire) and hence, via the constraint, not-a: every
% 1-decision branch derives a = 0. The whole program reverses polarity:
%   k=0 : cautious = [b]a [b]-b [b]-c
%   k>=1: cautious = -a b c
% This is the presumption -> derivation handover of the single-crossing
% trajectory grammar; the swap is possible because the stable model has
% a bivalence gap on b (neither b nor -b holds in it).
a :- not b.
c :- b.
c :- -b.
:- a, c.
