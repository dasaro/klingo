#modeh(flip(var(c))).
#modeb(red(var(c))).
#modeb(blue(var(c))).
#modeb(card(var(c))).
#maxv(1).
card(c1).
card(c2).
card(c3).
card(c4).
red(c1).
red(c3).
blue(c2).
blue(c4).
#pos(p1, {flip(c1)}, {}).
#pos(p2, {flip(c3)}, {}).
#neg(n3, {flip(c2)}, {}).
#neg(n4, {flip(c4)}, {}).
