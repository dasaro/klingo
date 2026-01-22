% Training: 12 independent choices
1 { h(1); -h(1) } 1.
1 { h(2); -h(2) } 1.
1 { h(3); -h(3) } 1.
1 { h(4); -h(4) } 1.
1 { h(5); -h(5) } 1.
1 { h(6); -h(6) } 1.
1 { h(7); -h(7) } 1.
1 { h(8); -h(8) } 1.
1 { h(9); -h(9) } 1.
1 { h(10); -h(10) } 1.
1 { h(11); -h(11) } 1.
1 { h(12); -h(12) } 1.

% expose g to learn defaults that transfer
g(I) :- h(I).
t(I) :- g(I).

#show t/1.
#show -t/1.
