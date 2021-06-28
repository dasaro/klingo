x(1..9).
y(1..9).
n(1..9).

{sudoku(X,Y,N): n(N)}=1 :- x(X) ,y(Y).

{sudoku(X,Y,N) : y(Y)}=1 :- x(X), n(N).
{sudoku(X,Y,N) : x(X)}=1 :- y(Y), n(N).

subgrid(X,Y,A,B) :- x(X), x(A), y(Y), y(B),(X-1)/3 == (A-1)/3, (Y-1)/3 == (B-1)/3.

:- sudoku(X,Y,N), sudoku(A,Y,N), X!=A.
:- sudoku(X,Y,N), sudoku(X,B,N), Y!=B.
:- sudoku(X,Y,V), sudoku(A,B,V), subgrid(X,Y,A,B), X != A, Y != B.

#show sudoku/3.

sudoku(1,1,7).
sudoku(1,8,1).
sudoku(1,9,9).
sudoku(2,1,4).
sudoku(2,2,6).
sudoku(2,4,1).
sudoku(2,5,9).
sudoku(3,4,6).
sudoku(3,5,8).
sudoku(3,6,2).
sudoku(3,7,7).
sudoku(3,9,4).
sudoku(4,2,9).
sudoku(4,9,7).
sudoku(5,4,3).
sudoku(5,7,4).
sudoku(5,9,5).
sudoku(6,3,6).
sudoku(6,4,7).
sudoku(7,3,1).
sudoku(8,1,2).
sudoku(8,5,7).
sudoku(8,6,4).
sudoku(9,4,2).
sudoku(9,7,3).
