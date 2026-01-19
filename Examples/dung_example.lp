% Dung AF example with two stable extensions: {a,c} and {b}.

arg(a; b; c).

att(a,b).
att(b,a).
att(b,c).
att(c,b).

{in(X)} :- arg(X).
out(Y) :- in(X), att(X,Y).

:- in(X), in(Y), att(X,Y).
:- arg(X), not in(X), not out(X).

#show in/1.
