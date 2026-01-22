% learned rules
% source: Experiments/wason/rule_level/train.lp
flip(C) :- red(C), not -flip(C).
