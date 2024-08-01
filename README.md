# Abvio Repository

One of the things that I have always bemoaned is how bad input files are. But oh my god. I understand now that an input file with consistent and succinct syntax is so incredibly difficult to make. Rigidity and asking the user to learn how to write input files is far better than trying to anticipate all of the possibilities. If you are trying to add flexibility in an input file, it leads to unintended consequences that the user might be unaware of. Additionally, if there is more than one way to do something, then it becomes far too confusing (cough cough QuantumEspresso) 

Conversely, rigidity does not allow for users to solve new problems that the developer hasn't considered before. If an input file does not allow abstraction or flexibility, then the user is confined to the conventions that you have thrust upon them. 

Furthermore, rigid input files do not entirely solve the problem of unintended consequences. Specifically, if the program does not warn the user of unrecognized input tags, then that value is set to the default setting. I know this can be boiled down to "skill issue" or "bad software design", but there can be nefarious consequences to even long time users! 

One example I can provide is that I had been blissfully unaware of a misspelling in my INCAR file. No warning or strange behavior had come of it. A sample of my input file is the following

```
EDIFF = 1e-06
EDIFFG = -0.01
NSW = 100
NELM = 30
IBRION = 2
ENCUT = 600
IDVW = 11
LWAVE = False
LAECHG = True
```

This file will run a perfectly fine VASP calculation with no warnings. But when life gives you melons, you might have misspelled an INCAR tag. In particular, `IVDW` is a totally, absolutely fine abbreviation. Especially as a chemist I should be trained to recognize the short hand for van der Waals. But as an _American_, I must pin this on the developers as a silly thing to let slide.

In my angst (and also Covid quaruntine), I decided to take up a challenge of writing a better input file for VASP calculations. In doing so, I have created the aptly named `abvio` (a better VASP input and output) python package. Developing this project was metaphorical and actual fever dream. You might notice this in some of the hastily written doc strings and naming conventions. Thankfully, the abvio package comes with comprehensive tests so hopefully that will allow me (or someone who is foolish enough to make a PR) to polish the codebase up in a reasonable time frame. 

___

What I attempted to do is take a well understood data structure that provides both flexibility and convention and adorn in with ab initio jargon. This provides a few enormous benefits. One such benefit is that the foundation of your input file is well documented, tested, and understood by a wide audience. 

Specifically, I have chosen to use a yaml file. Although, it is less familiar to people than perhaps json or csv, yaml is quick to learn and easy to read (mostly).

The following is an example of what a spin-orbit coupled band structure calculation of fluorite looks like

```yaml

structure:
    mode: manual
    species: 
        Ca: 4
        F: 8
    lattice:
        a: 5.516052
        b: 5.516052
        c: 5.516052
        alpha: 90.0
        beta: 90.0
        gamma: 90.0
    coords: [
        [0.0, 0.0, 0.0],
        [0.0, 2.758, 2.758],
        [2.758, 0.0, 2.758],
        [2.758, 2.758, 0.0],
        [1.379, 4.137, 1.379],
        [1.379, 4.137, 4.137],
        [1.379, 1.379, 4.137],
        [1.379, 1.379, 1.379],
        [4.137, 4.137, 4.137],
        [4.137, 4.137, 1.379],
        [4.137, 1.379, 1.379],
        [4.137, 1.379, 4.137],
        ]
incar:
    ediff: 1e-6
    encut: 500
    nelm: 35
    ibrion: 2
    lsorbit: true
    lorbit: 11
    magmom:
        Ca: [0, 0, 1.0]
        F: [0, 0, 0]
kpoints:
    mode: autoline
    spacing: 30

```

Currently, I am still unsure if this is aesthetically or functionally better than any other input file. Maybe let me know what you think. 

What is nice about this format is that everything is in one place. You can understand the relation of your structure and what the program will do with it. For example, MAGMOM is no longer a mess of arithemtic. You can specify by species and provide an array of the spin-axes. Also, abvio can intelligently determine the band structure path of the input structure. All you have to do is specify the number of kpoints per path. 

If these options aren't what you want, this input file supports all modes of kpoints generation. 

What makes this easier to understand is that the methods are flexible, but the user must be aware of _state_. In this case, the `mode` parameter handles instances where state can change. This ensures that both the program and the user understand which method will be used to construct the structure and reciprocal space sampling scheme.

An even more terse inputs file can be used to demonstrate the convenience of this input file structure.

The following file does exactly the same as the previous, but in this case all we need to do is pass the canonical name of a specific structure type and the species that will fill the distinct sites. We then only need to pass modifications to the lattice parameter.

```yaml
structure:
    mode: prototype
    prototype: fluorite
    species: [Ca, F]
    lattice:
        a: 5.516052
incar:
    ediff: 1e-6
    encut: 500
    nelm: 35
    ibrion: 2
    lsorbit: true
    lorbit: 11
    magmom:
        Ca: [0, 0, 1.0]
        F: [0, 0, 0]
kpoints:
    mode: autoline
    spacing: 30
```

Finally, if we are feeling even lazier, we can pull structures from materials project directly (so long as you have an API key).


```yaml
structure:
    mode: external
    code: mp-2741
incar:
    ediff: 1e-6
    encut: 500
    nelm: 35
    ibrion: 2
    lsorbit: true
    lorbit: 11
    magmom:
        Ca: [0, 0, 1.0]
        F: [0, 0, 0]
kpoints:
    mode: autoline
    spacing: 30
```

Each of these files will create the same set of VASP input files (you can check the tests to see if I am telling the truth!). 

___

Input files, much like young grad students, need validation. In fact, I don't quite understand why some ab initio suites don't do some form of sanity check and just lets the calculations crash. Once again, yes due diligence of the user is paramount. But hey, sometimes people make mistakes. 

So, I have attempted to bake sanity checks, input validation, and some wisdom into the processing of the input file. If you end up using this code, many warnings (and possibly errors) will be brought to the users attention even before the calculation has started. This might prevent a millisecond long disaster on week-long slurm queues. 

___

If you want to try it out, feel free to take any of the above files and test them using the command line interface by running

```
abvio input.yaml -o /tmp
```

Which will write INCAR, KPOINTS, and POSCAR to the root tmp directory (just make sure you change the file name in the command to match your file name). 

You can also preview what the output should look like using 

```
abvio input.yaml --preview
```

Which will give an output like this

![cli preview](/docs/images/preview.png)