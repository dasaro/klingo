# k-lingo 0.0.2

#### REQUIREMENTS

k-lingo was implemented and tested on an Apple M1 Macbook Pro with a python-enabled clingo 5.4.0 and Python 3.7.4. You may find more information on how to install python-enabled clingo at the official website https://potassco.org/clingo/. We recommend using the anaconda python distribution, downloadable from https://www.anaconda.com/products/individual#Download.

#### USAGE

You must grant k-lingo execution permission with `chmod +x klingo`. Then, you can test k-lingo with one of the pre-defined examples in the `Examples` folder by running e.g. `./klingo -k <depth> Examples/example1.lp`.

#### CHANGELOG:

**v0.0.2**:

- README created
- Added options to control output format
- Output now clearly states when the input logic program is unsatisfisable
- Output now clearly states if the found 3ND*-valuation is total

**v0.0.1**:

- Git repository created.
- First alpha version uploaded.