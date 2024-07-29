# Incar Examples

Here are some examples to help the user understand how the new input file format works. 
__
## Basic Usage and Legacy Strings

The following is an example of how to perform a spin-polarized geometry optimization of magnetite (Fe3O4) pulled from materials project.

```yaml
incar:
	ediff:  1e-06
	ediffg: -0.01
	nsw:    25
	nelm:   300
	lwave:  false
	isif:   3
	ibrion: 2
	ispin:  2
	validation: true
	magmom:
		species:
			Fe: 5.0
			O: 0.0
	
poscar:
	mpapi: mp-19306
	cell: conventional

kpoints:
    scheme: gamma
    mesh: [7, 7, 7]
```

Alternatively, if you are working with a structure that you need to be more scrutinizing with, you can use the original convention in VASP if that is more familiar to you.


```yaml
incar:
        ediff:  1e-06
        ediffg: -0.01
        nsw:    25
        nelm:   300
        lwave:  false
        isif:   3
        ibrion: 2
        ispin:  2
        magmom: 
		string: 24*5 32*0

poscar:
        mpapi: mp-19306
        cell: conventional

kpoints:
    scheme: gamma
    divisions: [7, 7, 7]
```
___

