% Related task where learned defaults may be overridden at higher depth
% Learned default suggests q, but deeper search can derive -q via s.
p(a) :- q.
-q :- s.

% s becomes decided only with deeper search.
s :- not t.
t :- not s.

#show p/1.
#show q/0.
#show -q/0.
#show s/0.
#show t/0.
#show -s/0.
#show -t/0.
