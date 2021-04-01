x(1..4).
y(1..4).
n(1..4).

1{sudoku(X,Y,N): n(N)}1 :- x(X) ,y(Y).

subgrid(X,Y,A,B) :- x(X), x(A), y(Y), y(B), (X-1)/2 == (A-1)/2, (Y-1)/2 == (B-1)/2.

:- sudoku(X,Y,N), sudoku(A,Y,N), X!=A.
:- sudoku(X,Y,N), sudoku(X,B,N), Y!=B.
:- sudoku(X,Y,N), sudoku(A,B,N), subgrid(X,Y,A,B), X != A, Y != B.

sudoku(3,1,3).
sudoku(4,1,4).
sudoku(1,4,3).
