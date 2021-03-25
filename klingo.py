import clingo
import argparse

# GLOBAL PARAMS:
__version__ = "0.0.1"
k = 0
dictionary = False
debug = False
prg = clingo.Control()

def translateTruthValue(string):
    if string==True: return "1"
    elif string==False: return "0"
    elif string==None: return "⊥"

class Propagator:
    def init(self, init):
        init.check_mode = clingo.PropagatorCheckMode.Fixpoint
        self.solver_literals = []
        self.symbols = []

        for atom in init.symbolic_atoms:
            init.add_watch(init.solver_literal(atom.literal))
            self.solver_literals.append(init.solver_literal(atom.literal))
            self.symbols.append(atom.symbol)
            if dictionary: print(atom.symbol,"has solver literal",init.solver_literal(atom.literal))
        

    def check(self,ctl):
        if debug: print("Current depth = ", ctl.assignment.decision_level-1)

        if (ctl.assignment.decision_level == k+1) or ((ctl.assignment.is_total) and (ctl.assignment.decision_level < k+1)):
            print("3ND-valuation found:")
            for i in range(len(self.solver_literals)):
                print("V("+str(self.symbols[i])+") = "+translateTruthValue(ctl.assignment.value(self.solver_literals[i])))
            print("--------------------------------")
            prg.interrupt()

if __name__=="__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=str, help="path to lp file")
    parser.add_argument("-k", "--depth", type=int, help="depth of reasoner (default=0)", default=0)
    parser.add_argument("--dictionary", help="display the dictionary", action="store_true")
    parser.add_argument("--debug", help="display debug information", action="store_true")
    args = parser.parse_args()
    k = args.depth
    if args.debug: DEBUG = True
    if args.dictionary: DICTIONARY = True
    
    print("k-lingo version",__version__)
    print("Reading from",args.file)
    print("Running with k =",args.depth,"\n")
    
    prg.register_propagator(Propagator())
    prg.load(args.file)
    prg.ground([("base", [])])
    prg.solve(on_model=lambda m: None)
