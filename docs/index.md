# Welcome to abvio

Abvio ('a better VASP input and output) is a small project that attempts to simplify the creation of VASP input files. Much of the inspiration comes from QuantumEspresso, Psi4, and ASE - all packages that have made wonderful contributions to the user experience of ab-initio calculations. 

I hope this package is of use to you. 


## What abvio does

Abvio is a glorified yaml parser, at its highest level. It does not do anything other than read a user created file and create matching INCAR, KPOINTS, POSCAR, and POTCAR files. The novelty of abvio lies in its multitude of helper utilities that streamline the specification of tedious parameters like structural information, pseudopotential ordering, k-space sampling schemes, magnetic moments, and more. You can see a list of some features in the following section.

### Features
- Generation of POSCARs from materials project codes
- Automatic linemode k-path lookup 
- Validation of all input files and format
- Specification of default incar file parameters
- Notes section 
