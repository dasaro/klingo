% Property: three-status trajectory F -> UNDEC -> T for yes under --bnm.
% yes is in no stable model (presumed false at depth 0) but classically
% entailed by case enumeration over the bivalent pairs x1, x2 with
% refutation width 3, so the polarity handover passes through a
% suspension phase:
%   k=0 : yes cautiously false (cautious = -yes bait1 bait2 -x1 -x2)
%   k=1 : suspension           (cautious set empty)
%   k>=2: yes cautiously true  (cautious = yes)
yes :- x1, x2.
yes :- x1, -x2.
yes :- -x1, x2.
yes :- -x1, -x2.
bait1 :- not yes.
bait2 :- not yes.
