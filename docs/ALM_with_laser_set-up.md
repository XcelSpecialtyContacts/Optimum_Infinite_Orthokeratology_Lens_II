To eliminate the ALM from looking for a BC to FC clocking alignment mark on axial symetric parts with laser engraving a file in the ALM control software will need to be edited.

Edit the file named XASPFRNT.TPL

Search for the function named `set_c_zero`.
Once found, a few lines into the function you will see `ERROR = 0`.
Insert a line after this line.

`if {torics+bisym+dmn}+otpts = 0 m99'

Save the file.